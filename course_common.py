"""课程共用的读表、指标和绘图函数；所有数据均为模拟教学数据。"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
RESULTS = ROOT / 'results'
AS_OF = pd.Timestamp('2026-01-01')  # 排他上界；截至2025-12-31的快照
BLUE, TEAL, ORANGE = '#2878A5', '#238B80', '#D58B36'
CHANNELS = ['organic', 'paid_search', 'social', 'affiliate']

def load_tables():
    """返回独立副本；标识符保留文本，金额列单位一律为分。"""
    names = ['customers', 'products', 'sessions', 'orders', 'order_items',
             'marketing', 'inventory', 'experiment', 'reviews']
    tables = {name: pd.read_csv(DATA / f'{name}.csv') for name in names}
    for frame in tables.values():
        for col in frame.columns:
            if col.endswith('_date') or col in ['registered_at']:
                frame[col] = pd.to_datetime(frame[col], errors='raise')
    return tables

def build_facts(tables=None):
    """订单行事实表与订单事实表。订单头和订单行不可直接混加。"""
    t = load_tables() if tables is None else tables
    lines = t['order_items'].merge(t['orders'], on='order_id', how='left',
        validate='many_to_one', suffixes=('', '_order'))
    lines = lines.merge(t['products'], on='product_id', how='left', validate='many_to_one')
    assert len(lines) == len(t['order_items'])
    paid = lines['status'].ne('cancelled')
    lines['net_sales_cents'] = lines['paid_cents'] - lines['refund_cents']
    lines['shipped_units'] = np.where(paid, lines['quantity'], 0)
    lines['net_units'] = lines['shipped_units'] - lines['refunded_qty']
    # 教学假设：退货可按原成本重新入库，平台费随净额退回。
    lines['cogs_cents'] = lines['net_units'] * lines['unit_cost_cents']
    lines['platform_fee_cents'] = np.rint(lines['net_sales_cents'] * .03).astype('int64')
    count = lines.groupby('order_id')['line_id'].transform('size')
    position = lines.groupby('order_id').cumcount()
    fee = lines['fulfilment_fee_cents']
    # 用整除和余数分配，保证每单800分只分配一次，且不丢失一分钱。
    lines['allocated_fulfilment_cents'] = fee // count + (position < (fee % count)).astype(int)
    lines['contribution_cents'] = (lines['net_sales_cents'] - lines['cogs_cents']
        - lines['platform_fee_cents'] - lines['allocated_fulfilment_cents'])
    totals = lines.groupby('order_id', as_index=False).agg(
        net_sales_calc=('net_sales_cents', 'sum'), net_units=('net_units', 'sum'),
        cogs_cents=('cogs_cents', 'sum'), platform_fee_cents=('platform_fee_cents', 'sum'),
        allocated_fulfilment_cents=('allocated_fulfilment_cents', 'sum'),
        contribution_cents=('contribution_cents', 'sum'))
    orders = t['orders'].merge(totals, on='order_id', validate='one_to_one')
    assert (orders['net_sales_calc'] == orders['paid_total_cents'] - orders['refund_total_cents']).all()
    assert (orders['allocated_fulfilment_cents'] == orders['fulfilment_fee_cents']).all()
    return lines, orders

def positive_orders():
    """RFM和客户留存使用净商品收入>0的订单；不含取消或全额退款单。"""
    _, orders = build_facts()
    return orders.loc[orders['net_sales_calc'].gt(0)].copy()

def rfm_table():
    o = positive_orders()
    rfm = o.groupby('customer_id').agg(last_date=('order_date', 'max'),
        frequency=('order_id', 'nunique'), monetary_cents=('net_sales_calc', 'sum'))
    rfm['recency_days'] = (AS_OF - rfm['last_date']).dt.days
    return rfm.reset_index()

def safe_divide(numerator, denominator):
    """0分母返回NaN，不能用0伪装没有定义的比率。"""
    if isinstance(denominator, pd.Series):
        return numerator / denominator.replace(0, np.nan)
    return numerator / denominator if denominator else np.nan

def outdir(number):
    folder = RESULTS / f'lesson_{number:02d}'
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def save_table(frame, number, name):
    path = outdir(number) / f'{name}.csv'
    frame.to_csv(path, encoding='utf-8-sig', index=False)
    return path

def setup_plot():
    installed = {f.name for f in font_manager.fontManager.ttflist}
    candidates = ['Microsoft YaHei', 'Noto Sans CJK SC', 'SimHei', 'DejaVu Sans']
    plt.rcParams.update({'font.family': [x for x in candidates if x in installed],
        'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
        'axes.unicode_minus': False, 'figure.facecolor': 'white'})

def save_figure(fig, number, name):
    setup_plot()
    fig.text(.02, .01, 'SYNTHETIC TEACHING DATA', fontsize=7, color='#687A86')
    fig.tight_layout(rect=(0, .035, 1, 1))
    path = outdir(number) / f'{name}.png'
    fig.savefig(path, dpi=180, facecolor='white')
    import sys
    if '--show' in sys.argv:
        plt.show()
    plt.close(fig)
    return path

def show(frame, rows=10):
    print(frame.head(rows).to_string(index=False))

setup_plot()
