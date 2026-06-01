import unittest
import os
import shutil
from pathlib import Path
from utils.chart_generator_mpl import generate_chart_mpl

class TestChartGenerators(unittest.TestCase):
    def setUp(self):
        # Sample mock OHLCV data (10 candles)
        self.mock_ohlcv = [
            {"time": 1716240000000 + i * 3600000, "open": 100 + i, "high": 105 + i, "low": 98 + i, "close": 102 + i, "volume": 1000 * i}
            for i in range(10)
        ]
        self.temp_dir = Path(__file__).resolve().parent / "temp_charts"
        self.temp_dir.mkdir(exist_ok=True)
        
    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            
    def test_mpl_generator_dict_format(self):
        save_path = self.temp_dir / "test_chart_dict.png"
        drawings = [
            {"price": 104.5, "label": "Entry", "color": "#26a69a"},
            {"price": 99.0, "label": "Stop Loss", "color": "#ef5350"},
            {"price": 112.0, "label": "Take Profit", "color": "#2962ff"}
        ]
        strategy_table = {
            "title": "SEPA Strategy",
            "rows": [
                ("Pattern", "VCP"),
                ("ATR", "2.4"),
                ("Score", "92%")
            ]
        }
        
        result_path = generate_chart_mpl(
            symbol="BTCUSDT",
            timeframe="1h",
            ohlcv_data=self.mock_ohlcv,
            drawings=drawings,
            strategy_table=strategy_table,
            save_path=save_path
        )
        
        self.assertTrue(result_path.exists())
        self.assertEqual(result_path, save_path)
        self.assertGreater(os.path.getsize(result_path), 1000)

    def test_mpl_generator_list_format(self):
        # [[timestamp, open, high, low, close, volume], ...]
        list_ohlcv = [
            [1716240000000 + i * 3600000, 100 + i, 105 + i, 98 + i, 102 + i, 1000 * i]
            for i in range(10)
        ]
        save_path = self.temp_dir / "test_chart_list.png"
        
        result_path = generate_chart_mpl(
            symbol="ETHUSDT",
            timeframe="15m",
            ohlcv_data=list_ohlcv,
            save_path=save_path
        )
        
        self.assertTrue(result_path.exists())
        self.assertEqual(result_path, save_path)
        self.assertGreater(os.path.getsize(result_path), 1000)

import pytest
from utils.chart_generator_lw import generate_chart_lw

@pytest.mark.asyncio
async def test_playwright_generator():
    mock_ohlcv = [
        {"time": 1716240000000 + i * 3600000, "open": 100 + i, "high": 105 + i, "low": 98 + i, "close": 102 + i, "volume": 1000 * i}
        for i in range(10)
    ]
    temp_dir = Path(__file__).resolve().parent / "temp_charts_lw"
    temp_dir.mkdir(exist_ok=True)
    save_path = temp_dir / "test_chart_lw.png"
    
    try:
        result_path = await generate_chart_lw(
            symbol="BTCUSDT",
            timeframe="1h",
            ohlcv_data=mock_ohlcv,
            drawings=[{"price": 105.0, "label": "Target", "color": "#26a69a"}],
            strategy_table={"title": "Test Table", "rows": [("Metric", "Val")]},
            save_path=save_path
        )
        assert result_path.exists()
        assert result_path == save_path
        assert os.path.getsize(result_path) > 1000
    finally:
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

