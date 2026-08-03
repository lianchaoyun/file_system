"""
convert_tdx_2_csv.py - 生成 qlib 可用的 CSV 数据（股票+指数统一入口）

支持三种模式:
    --mode all    : 股票+指数一起处理（默认），每批股票末尾追加指数，一次API拉取
    --mode stock  : 仅股票（含后复权因子，与 DuckDB 管道统一）
    --mode index  : 仅指数（无复权因子）

输出目录: ./data/qlib/tdx/csv/{SH600519}.csv (股票+指数统一存放)

CSV 格式:
    股票: date,open,high,low,close,volume,factor
    指数: date,open,high,low,close,volume

用法:
    python convert_tdx_2_csv.py                        # 默认 all 模式
    python convert_tdx_2_csv.py --mode stock           # 仅股票
    python convert_tdx_2_csv.py --mode index           # 仅指数
    python convert_tdx_2_csv.py --start 20230101 --batch 100
"""
import sys
import os
from pathlib import Path

# ---- 从 ai 目录运行时，加载通达信量化模块 ----
TDX_PLUGINS = r"D:\app\tdxmock\PYPlugins"
sys.path.insert(0, os.path.join(TDX_PLUGINS, "user"))

# ---- 加载 src/ 目录以导入公共模块 ----
_SELF = Path(__file__).resolve()
SRC_DIR = str(_SELF.parents[2])  # ts/tdx/ → src/
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from tqcenter import tq
from common.index_list import get_index_list
import pandas as pd
import numpy as np
import time
from datetime import datetime


# ==================== 辅助函数 ====================

def calc_backward_factor(df_kline, divid_df):
    """
    根据除权除息数据计算后复权因子（与 DuckDB 管道统一）

    后复权: 近期价格保持不变，历史数据向上调整。
    factor[t] = 1 / ∏ f_i  （所有在日期 t 之前发生的除权事件）

    参数:
        df_kline: K线 DataFrame，按日期升序排列，含 date, close 列
        divid_df: 除权除息 DataFrame，索引=除权日，列: Bonus, AllotPrice, ShareBonus, Allotment

    返回:
        factor 数组，长度 = len(df_kline)，可用于 close * factor 得到后复权价格

    优势:
        - 新增分红时，只需重新计算分红日之后的数据，历史 factor 不受影响。
        - 使用 numpy 向量化 mask 替代 Python 循环，性能大幅提升。
    """
    n = len(df_kline)
    factor = np.ones(n)

    if divid_df.empty:
        return factor

    kline_dates = pd.to_datetime(df_kline['date']).values

    # ──── Step 1: 计算每个除权事件的单次因子 ────
    events = []  # [(ex_date_np, f), ...]
    for ex_date, row in divid_df.iterrows():
        bonus = row['Bonus'] / 10.0
        share_bonus = row['ShareBonus'] / 10.0
        allotment = row['Allotment'] / 10.0
        allot_price = row['AllotPrice']

        # 二分查找除权日前一个交易日在 kline_dates 中的位置
        prev_day = np.datetime64(ex_date - pd.Timedelta(days=1))
        prev_idx = np.searchsorted(kline_dates, prev_day, side='right') - 1
        if prev_idx < 0:
            continue

        close_before = df_kline.iloc[prev_idx]['close']
        if close_before <= 0:
            continue

        # 除权后理论价与单次因子 f = close_after / close_before
        close_after = (close_before - bonus + allotment * allot_price) \
                    / (1 + share_bonus + allotment)
        f = close_after / close_before

        if f <= 0 or np.isnan(f) or np.isinf(f):
            continue

        events.append((np.datetime64(ex_date), f))

    # ──── Step 2: 后复权 - 按时间升序，除权日及之后的所有日期 ÷ f ────
    events.sort(key=lambda x: x[0])
    for evt_date, f in events:
        mask = kline_dates >= evt_date
        factor[mask] /= f

    return factor


def code_to_symbol(code: str) -> str:
    """将 '688318.SH' 转为 'SH688318'"""
    parts = code.split('.')
    if len(parts) == 2:
        return parts[1] + parts[0]
    return code


def process_single(code, kline_result, output_dir, need_factor=False, 
                   start_date=None, end_date=None):
    """
    统一处理单个标的（股票或指数）

    参数:
        code:         股票/指数代码，如 '000001.SZ', '000001.SH'
        kline_result: tq.get_market_data 返回的结果
        output_dir:   CSV 输出目录
        need_factor:  是否需要计算复权因子（股票=True, 指数=False）
        start_date:   起始日期（仅 need_factor=True 时需要）
        end_date:     结束日期（仅 need_factor=True 时需要）
    """
    # ---- 提取 K线数据 ----
    close_field = kline_result.get('Close', pd.DataFrame())
    if code not in close_field.columns:
        return

    dates = close_field.index
    df = pd.DataFrame({
        'date':   dates.strftime('%Y-%m-%d'),
        'open':   kline_result['Open'][code].values,
        'high':   kline_result['High'][code].values,
        'low':    kline_result['Low'][code].values,
        'close':  close_field[code].values,
        'volume': kline_result['Volume'][code].values,
    })

    # 删除含有 NaN 的行
    df = df.dropna(subset=['open', 'close']).reset_index(drop=True)
    if df.empty:
        return

    # ---- 股票：获取除权除息数据 + 计算复权因子 ----
    if need_factor:
        divid_df = tq.get_divid_factors(
            stock_code=code,
            start_time=start_date,
            end_time=end_date,
        )
        df['factor'] = calc_backward_factor(df, divid_df)

    # ---- 保存 CSV ----
    symbol = code_to_symbol(code)
    csv_path = os.path.join(output_dir, f'{symbol}.csv')
    df.to_csv(csv_path, index=False, encoding='utf-8')
    type_label = "股票" if need_factor else "指数"
    print(f"    [OK] {code} ({type_label}) -> {len(df)} 条 ({symbol}.csv)")


# ==================== 主函数 ====================

def main(
    mode: str = 'all',
    output_dir: str = './data/stocka/tdx/csv',
    period: str = '1d',
    start_date: str = '20200101',
    end_date: str = None,
    batch_size: int = 50,
):
    """
    获取股票/指数 K线数据，保存为 Qlib CSV 格式（统一输出到同一个目录）

    参数:
        mode:        'all' / 'stock' / 'index'
        output_dir:  CSV 输出目录
        period:      K线周期 ('1d', '1w', '1m')
        start_date:  起始日期 YYYYMMDD
        end_date:    结束日期 YYYYMMDD，默认今天
        batch_size:  每批处理数量
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')
    tq.initialize(__file__)

    # ---- 准备目录 ----
    os.makedirs(output_dir, exist_ok=True)

    # ========== 收集待处理标的列表 ==========
    tasks = []  # (code, need_factor)

    # ---- 股票列表 ----
    if mode in ('all', 'stock'):
        print("=" * 50)
        print("获取股票列表...")
        stock_list = tq.get_stock_list('5', list_type=1)
        stock_codes = [s['Code'] for s in stock_list]
        print(f"[OK] 共 {len(stock_codes)} 只股票")
        for c in stock_codes:
            tasks.append((c, True))

    # ---- 指数列表 ----
    if mode in ('all', 'index'):
        print("=" * 50)
        print("加载指数列表...")
        index_list = get_index_list()
        index_codes = [idx['code'] for idx in index_list]
        print(f"[OK] 共 {len(index_codes)} 个指数")
        for idx in index_list:
            print(f"   - {idx['code']:15s} {idx['name']}")
        for c in index_codes:
            tasks.append((c, False))

    # ---- 映射：need_factor 字典 ----
    need_factor_map = {code: nf for code, nf in tasks}

    # ========== 批次处理 ==========
    if mode in ('all', 'stock'):
        # 股票需要分批，指数追加到每批末尾
        _stock_codes = [c for c, nf in tasks if nf]
        _index_codes = [c for c, nf in tasks if not nf]
        total_batches = (len(_stock_codes) + batch_size - 1) // batch_size

        print("\n" + "=" * 50)
        print(f"分批处理：{total_batches} 批（每批 {batch_size} 只股票 + {len(_index_codes)} 个指数）...")

        for batch_idx in range(total_batches):
            s_start = batch_idx * batch_size
            s_end = min(s_start + batch_size, len(_stock_codes))
            batch_codes = _stock_codes[s_start:s_end]  # 本批股票

            # 指数追加到每批末尾（all 模式一次 API 调用同时拉取）
            if mode in ('all', 'index'):
                api_codes = batch_codes + _index_codes
            else:
                api_codes = batch_codes

            print(f"\n  批次 {batch_idx + 1}/{total_batches}：股票 {s_start+1}~{s_end}，共 {len(api_codes)} 个标的")

            try:
                result = tq.get_market_data(
                    field_list=['Open', 'High', 'Low', 'Close', 'Volume'],
                    stock_list=api_codes,
                    period=period,
                    dividend_type='none',
                    start_time=start_date,
                    end_time=end_date,
                )
            except Exception as e:
                print(f"  [错误] API 调用失败: {e}")
                continue

            # 处理本批所有标的（股票 + 指数）
            for code in api_codes:
                need_factor = need_factor_map.get(code, False)
                process_single(code, result, output_dir,
                               need_factor=need_factor,
                               start_date=start_date,
                               end_date=end_date)

            time.sleep(0.5)

    elif mode == 'index':
        # 纯指数模式：一次拉取全部
        _index_codes = [c for c, nf in tasks]
        print("\n" + "=" * 50)
        print(f"获取指数K线数据（{len(_index_codes)} 个）...")
        print(f"  时间范围: {start_date} ~ {end_date}")

        result = tq.get_market_data(
            field_list=['Open', 'High', 'Low', 'Close', 'Volume'],
            stock_list=_index_codes,
            period=period,
            dividend_type='none',
            start_time=start_date,
            end_time=end_date,
        )

        print("\n" + "=" * 50)
        print("保存指数 CSV...")
        for code in _index_codes:
            process_single(code, result, output_dir,
                           need_factor=False)
            time.sleep(0.1)

    # ---- 总结 ----
    stock_count = sum(1 for _, nf in tasks if nf)
    index_count = sum(1 for _, nf in tasks if not nf)
    print(f"\n[OK] 全部完成！")
    print(f"  股票: {stock_count} 只, 指数: {index_count} 个 → {output_dir}")


# ==================== 入口 ====================

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='通达信 K线 → Qlib CSV')
    parser.add_argument('--mode', default='all', choices=['all', 'stock', 'index'])
    parser.add_argument('--start', default='20200101', help='起始日期 YYYYMMDD')
    parser.add_argument('--end', default=None, help='结束日期 YYYYMMDD')
    parser.add_argument('--batch', type=int, default=50, help='批大小')
    args = parser.parse_args()
    main(
        mode=args.mode,
        start_date=args.start,
        end_date=args.end,
        batch_size=args.batch,
    )
