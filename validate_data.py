"""核对主键、外键、金额、漏斗与库存守恒，避免业务口径错误。"""
import numpy as np
from course_common import load_tables,build_facts,AS_OF

def validate():
    t=load_tables();o=t['orders'];i=t['order_items'];s=t['sessions'];inv=t['inventory']
    for name,key in [('orders','order_id'),('order_items','line_id'),('customers','customer_id'),('products','product_id'),('sessions','session_id'),('experiment','visitor_id')]:
        assert t[name][key].is_unique and t[name][key].notna().all(),name
    assert set(i.order_id)<=set(o.order_id)
    assert set(i.product_id)<=set(t['products'].product_id)
    assert set(o.session_id)<=set(s.session_id)
    assert set(o.customer_id)<=set(t['customers'].customer_id)
    assert i.paid_cents.ge(i.refund_cents).all() and i.refund_cents.ge(0).all()
    assert i.refunded_qty.between(0,i.quantity).all()
    assert o.order_date.lt(AS_OF).all()
    refunds=i.loc[i.refunded_qty.gt(0)].merge(o[['order_id','order_date']],on='order_id',validate='many_to_one')
    assert refunds.refund_date.ge(refunds.order_date.dt.normalize()).all()
    assert refunds.refund_date.lt(AS_OF).all()
    sums=i.groupby('order_id')[['paid_cents','refund_cents']].sum()
    check=o.set_index('order_id').join(sums)
    assert check.paid_total_cents.eq(check.paid_cents).all()
    assert check.refund_total_cents.eq(check.refund_cents).all()
    assert (s.viewed_product>=s.added_cart).all() and (s.added_cart>=s.checkout).all()
    assert (s.checkout>=s.placed_order).all() and (s.placed_order>=s.paid_order).all()
    assert s.paid_order.sum()==o.paid_total_cents.gt(0).sum()
    assert (inv.opening_qty+inv.inbound_qty+inv.restock_qty-inv.shipped_qty==inv.closing_qty).all()
    next_open=inv.sort_values(['product_id','inventory_date']).groupby('product_id').opening_qty.shift(-1)
    sorted_inv=inv.sort_values(['product_id','inventory_date'])
    assert sorted_inv.loc[next_open.notna(),'closing_qty'].eq(next_open.dropna()).all()
    assert inv.closing_qty.ge(0).all()
    paid_lines=i.merge(o[['order_id','status']],on='order_id',validate='many_to_one')
    assert inv.shipped_qty.sum()==paid_lines.loc[paid_lines.status.ne('cancelled'),'quantity'].sum()
    assert inv.restock_qty.sum()==i.refunded_qty.sum()
    lines,facts=build_facts(t)
    assert lines.contribution_cents.sum()==facts.contribution_cents.sum()
    assert lines.allocated_fulfilment_cents.sum()==o.fulfilment_fee_cents.sum()
    return {'primary_keys':True,'foreign_keys':True,'money_reconciled':True,'funnel_nested':True,'inventory_conserved':True,'cost_allocation_conserved':True}

if __name__=='__main__':print(validate())
