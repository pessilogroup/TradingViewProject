"""
rag.py — RAG (Retrieval-Augmented Generation) Module
Tích hợp ChromaDB + Sentence Transformers + Claude (Anthropic) vào FastAPI backend.

Flow:
    1. init_vector_db()  → Đọc 36 chunk Minervini, embed và lưu vào ChromaDB
    2. query_knowledge() → Truy vấn theo semantic similarity
    3. generate_trading_advice() → Gọi Claude API để phân tích tín hiệu
"""

import logging
import re
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

import importlib.util

CHROMADB_AVAILABLE = importlib.util.find_spec("chromadb") is not None
ANTHROPIC_AVAILABLE = importlib.util.find_spec("anthropic") is not None
GENAI_AVAILABLE = importlib.util.find_spec("google.generativeai") is not None
VERTEXAI_AVAILABLE = importlib.util.find_spec("vertexai") is not None

if not CHROMADB_AVAILABLE:
    log.warning("chromadb not installed. Run: pip install chromadb sentence-transformers")
if not ANTHROPIC_AVAILABLE:
    log.warning("anthropic not installed. Run: pip install anthropic")
if not GENAI_AVAILABLE:
    log.warning("google-generativeai not installed. Run: pip install google-generativeai")
if not VERTEXAI_AVAILABLE:
    log.warning("vertexai not installed. Run: pip install google-cloud-aiplatform")

import config

# ── Globals ────────────────────────────────────────────────────────────────
_chroma_client: Optional[object] = None
_collection: Optional[object] = None


def _get_embedding_function():
    """Dùng sentence-transformers local (không cần API key, miễn phí)."""
    if not CHROMADB_AVAILABLE:
        return None
    from chromadb.utils import embedding_functions
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="paraphrase-multilingual-MiniLM-L12-v2"  # hỗ trợ tiếng Việt
    )


def _parse_chunk_metadata(content: str, filename: str) -> dict:
    """Extract metadata từ header của mỗi file chunk Markdown."""
    meta = {"filename": filename, "topic": "general", "chapter": ""}
    # Lấy dòng đầu tiên làm title
    lines = content.strip().splitlines()
    for line in lines:
        if line.startswith("# "):
            meta["topic"] = line.lstrip("# ").strip()
            break
    # Extract chapter info từ tên file (chunk_001.md → 001)
    match = re.search(r"chunk_(\d+)", filename)
    if match:
        meta["chapter"] = match.group(1)
    return meta


async def init_vector_db() -> bool:
    """
    Khởi tạo ChromaDB và embed tất cả Markdown chunks vào Vector DB.
    Được gọi trong FastAPI lifespan startup.

    Returns:
        True nếu thành công, False nếu không có packages cần thiết.
    """
    global _chroma_client, _collection

    if not CHROMADB_AVAILABLE:
        log.error("RAG unavailable: chromadb not installed.")
        return False

    knowledge_dir = Path(config.KNOWLEDGE_DIR)
    if not knowledge_dir.exists():
        log.error(f"RAG: Knowledge dir not found: {knowledge_dir}")
        return False

    chunk_files = sorted(knowledge_dir.glob("chunk_*.md"))
    if not chunk_files:
        log.warning(f"RAG: No chunk files found in {knowledge_dir}")
        return False

    # Khởi tạo ChromaDB (lưu persistent vào disk)
    chroma_db_path = Path(config.CHROMA_DB_PATH)
    chroma_db_path.mkdir(parents=True, exist_ok=True)

    import chromadb
    _chroma_client = chromadb.PersistentClient(path=str(chroma_db_path))
    ef = _get_embedding_function()

    _collection = _chroma_client.get_or_create_collection(
        name="minervini_knowledge",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    # Kiểm tra xem đã embed chưa (tránh re-embed mỗi lần restart)
    existing_count = _collection.count()
    if existing_count >= len(chunk_files):
        log.info(
            f"RAG: Vector DB đã có {existing_count} vectors. Bỏ qua re-embedding."
        )
        return True

    log.info(f"RAG: Bắt đầu embed {len(chunk_files)} Minervini chunks → ChromaDB...")

    documents, metadatas, ids = [], [], []

    for chunk_file in chunk_files:
        try:
            content = chunk_file.read_text(encoding="utf-8")
            if not content.strip():
                continue
            meta = _parse_chunk_metadata(content, chunk_file.name)
            doc_id = f"minervini_{chunk_file.stem}"

            documents.append(content)
            metadatas.append(meta)
            ids.append(doc_id)
        except Exception as e:
            log.warning(f"RAG: Lỗi đọc {chunk_file.name}: {e}")

    if documents:
        # Upsert theo batch (tránh timeout với nhiều docs)
        batch_size = 10
        for i in range(0, len(documents), batch_size):
            _collection.upsert(
                documents=documents[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
                ids=ids[i : i + batch_size],
            )
        log.info(f"RAG: ✅ Đã embed và lưu {len(documents)} chunks vào ChromaDB.")

    return True


def query_knowledge(query: str, n_results: int = 3) -> list[dict]:
    """
    Truy vấn Vector DB để tìm các đoạn Minervini liên quan nhất.

    Args:
        query: Câu truy vấn ngữ nghĩa (vd: "Quy tắc mua khi VCP breakout")
        n_results: Số lượng kết quả trả về (mặc định 3)

    Returns:
        List of dicts với keys: 'content', 'metadata', 'distance'
    """
    if _collection is None:
        log.warning("RAG: Collection chưa được khởi tạo.")
        return []

    try:
        results = _collection.query(
            query_texts=[query],
            n_results=min(n_results, _collection.count()),
        )

        output = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, distances):
            output.append({
                "content": doc,
                "metadata": meta,
                "relevance_score": round(1 - dist, 4),  # cosine similarity
            })

        log.info(f"RAG: Query '{query[:50]}...' → {len(output)} chunks retrieved.")
        return output

    except Exception as e:
        log.error(f"RAG query error: {e}")
        return []


async def generate_trading_advice(
    symbol: str,
    action: str,
    price: str,
    payload: dict,
    rag_chunks: list[dict],
) -> str:
    """
    Gọi Claude (Anthropic) để phân tích tín hiệu giao dịch dựa trên kiến thức Minervini.

    Args:
        symbol: Mã cổ phiếu/crypto (vd: "BTCUSDT")
        action: "buy" | "sell" | "alert"
        price: Giá hiện tại
        payload: Full webhook payload từ TradingView
        rag_chunks: Các đoạn kiến thức Minervini được retrieve

    Returns:
        Chuỗi phân tích từ Claude, hoặc thông báo lỗi.
    """
    provider = getattr(config, "AI_PROVIDER", "anthropic").lower()

    if provider == "gemini":
        has_vertex = VERTEXAI_AVAILABLE and getattr(config, "GCP_PROJECT_ID", None)
        has_genai = GENAI_AVAILABLE and getattr(config, "GEMINI_API_KEY", None)
        if not (has_vertex or has_genai):
            return "⚠️ RAG Analysis không khả dụng (thiếu GEMINI_API_KEY hoặc GCP_PROJECT_ID)."
    else:
        if not ANTHROPIC_AVAILABLE or not getattr(config, "ANTHROPIC_API_KEY", None):
            return "⚠️ RAG Analysis không khả dụng (thiếu ANTHROPIC_API_KEY)."

    if not rag_chunks:
        return "⚠️ Không tìm thấy kiến thức phù hợp trong Knowledge Base."

    # ── Xây dựng context từ các chunks retrieved ─────────────────────────
    context_parts = []
    for i, chunk in enumerate(rag_chunks, 1):
        meta = chunk.get("metadata", {})
        score = chunk.get("relevance_score", 0)
        topic = meta.get("topic", "N/A")
        content_preview = chunk["content"][:800]  # giới hạn context
        context_parts.append(
            f"[Tài liệu {i} | Chủ đề: {topic} | Độ liên quan: {score:.2%}]\n{content_preview}"
        )

    knowledge_context = "\n\n---\n\n".join(context_parts)

    # ── Extra market data từ payload ──────────────────────────────────────
    volume = payload.get("volume", "N/A")
    volume_avg = payload.get("volume_avg", "N/A")
    rsi = payload.get("rsi", "N/A")
    alert_type = payload.get("alert_type", action)
    timeframe = payload.get("timeframe", "N/A")

    prompt = f"""Bạn là chuyên gia giao dịch theo phương pháp SEPA của Mark Minervini.
Dưới đây là tín hiệu TradingView vừa nhận được và các quy tắc liên quan từ sách của Minervini.

## TÍN HIỆU GIAO DỊCH
- **Mã**: {symbol}
- **Hành động**: {action.upper()}
- **Giá**: {price}
- **Loại tín hiệu**: {alert_type}
- **Khung thời gian**: {timeframe}
- **Volume hiện tại**: {volume}
- **Volume trung bình**: {volume_avg}
- **RSI**: {rsi}

## KIẾN THỨC MINERVINI LIÊN QUAN (từ Knowledge Base)
{knowledge_context}

## YÊU CẦU PHÂN TÍCH
Dựa trên tín hiệu trên và quy tắc của Minervini trong Knowledge Base:
1. **Đánh giá chất lượng tín hiệu** (Mạnh/Trung bình/Yếu) và lý do ngắn gọn
2. **Điểm phù hợp với Minervini** (có đáp ứng Trend Template, VCP, Volume không?)
3. **Khuyến nghị hành động** (Mua/Bán/Chờ thêm xác nhận) + Stop-loss gợi ý
4. **Cảnh báo rủi ro** (nếu có)

Trả lời NGẮN GỌN, súc tích (dưới 200 từ), dùng emoji để dễ đọc trên Telegram."""

    try:
        if provider == "gemini":
            model_name = "gemini-2.5-flash"
            
            _use_vertex = False
            if has_vertex:
                try:
                    import google.auth
                    google.auth.default()
                    _use_vertex = True
                except Exception:
                    log.warning("Vertex AI ADC not found — falling back to GEMINI_API_KEY")

            if _use_vertex:
                import vertexai
                from vertexai.generative_models import GenerativeModel as VertexGenerativeModel
                vertexai.init(project=config.GCP_PROJECT_ID, location=getattr(config, "GCP_LOCATION", "us-central1"))
                g_model = VertexGenerativeModel(model_name)
                response = g_model.generate_content(prompt)
                advice = response.text
            elif has_genai:
                import google.generativeai as genai
                genai.configure(api_key=config.GEMINI_API_KEY)
                g_model = genai.GenerativeModel(model_name)
                response = g_model.generate_content(prompt)
                advice = response.text
            else:
                return "⚠️ RAG Analysis không khả dụng (thiếu Gemini auth)."
            
            log.info(f"RAG: Gemini generated advice for {symbol} ({action})")
            return advice
        else:
            import anthropic
            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            message = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            advice = message.content[0].text
            log.info(f"RAG: Claude generated advice for {symbol} ({action})")
            return advice

    except Exception as e:
        log.error(f"RAG API error: {e}")
        return f"⚠️ Lỗi kết nối AI API: {str(e)[:100]}"


def build_rag_query(symbol: str, action: str, payload: dict) -> str:
    """
    Tạo câu truy vấn ngữ nghĩa tối ưu từ webhook payload.
    """
    alert_type = payload.get("alert_type", "")
    volume = payload.get("volume", 0)
    volume_avg = payload.get("volume_avg", 0)

    base = f"Quy tắc giao dịch Minervini khi {action}"

    if "vcp" in alert_type.lower() or "volatility contraction" in alert_type.lower():
        return f"VCP Volatility Contraction Pattern breakout điểm mua pivot {base}"
    if "trend template" in alert_type.lower():
        return f"Trend Template 8 tiêu chí Stage 2 xác nhận {base}"
    if volume and volume_avg:
        try:
            if float(volume) > float(volume_avg) * 1.5:
                return f"Volume nổ gấp đôi tăng bất thường xác nhận breakout {base}"
        except (TypeError, ValueError):
            pass
    if action == "buy":
        return f"Điểm mua tối ưu SEPA pivot breakout Stage 2 {symbol} {base}"
    if action == "sell":
        return f"Tín hiệu bán stop loss trailing stop quản lý vị thế {base}"

    return f"Quy tắc phân tích tín hiệu kỹ thuật SEPA Minervini {symbol} {base}"
