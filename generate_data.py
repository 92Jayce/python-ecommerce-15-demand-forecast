"""固定种子生成可复现的模拟店铺数据，不连接真实店铺或外部网站。"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
SEED = 20261028
AS_OF = pd.Timestamp('2026-01-01')

def generate():
    DATA.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    days = pd.date_range('2025-01-01', '2025-12-31', freq='D')
    channels = np.array(['organic', 'paid_search', 'social', 'affiliate'])
    categories = ['家居', '数码', '个护', '食品']
    products = pd.DataFrame({'product_id': [f'P{i:03}' for i in range(1,25)],
        'product_name': [f'{categories[i//6]}商品{i%6+1}' for i in range(24)],
        'category': [categories[i//6] for i in range(24)],
        'list_price_cents': rng.integers(1900, 25000, 24)})
    products['unit_cost_cents'] = np.rint(products['list_price_cents'] * rng.uniform(.35,.68,24)).astype(int)
    n = 22000
    day_weights = .8 + np.arange(365) / 365 * .4
    day_weights += np.where((days.month==11)&(days.day>=8)&(days.day<=12), 1.5, 0)
    day_weights += np.where((days.month==6)&(days.day>=16)&(days.day<=20), 1.0, 0)
    date_idx = rng.choice(365,n,p=day_weights/day_weights.sum())
    session_dates = days[date_idx] + pd.to_timedelta(rng.integers(0,86400,n), unit='s')
    customer_weights = rng.lognormal(0,.75,1200);customer_weights /= customer_weights.sum()
    customer_idx = rng.choice(1200,n,p=customer_weights)
    channel_idx = rng.choice(4,n,p=[.34,.29,.24,.13])
    viewed = rng.random(n)<.96
    cart = viewed & (rng.random(n)<np.array([.42,.49,.43,.46])[channel_idx])
    checkout = cart & (rng.random(n)<.62)
    placed = checkout & (rng.random(n)<.68)
    sessions = pd.DataFrame({'session_id':[f'S{i:06}' for i in range(1,n+1)],
        'customer_id':[f'C{i+1:04}' for i in customer_idx], 'session_date':session_dates,
        'channel':channels[channel_idx], 'device':rng.choice(['mobile','desktop'],n,p=[.74,.26]),
        'viewed_product':viewed.astype(int),'added_cart':cart.astype(int),
        'checkout':checkout.astype(int),'placed_order':placed.astype(int)})
    first_visit=sessions.groupby('customer_id')['session_date'].min()
    customer_rows=[]
    for i in range(1200):
        cid=f'C{i+1:04}';first=first_visit.get(cid,AS_OF-pd.Timedelta(days=5))
        registered=max(pd.Timestamp('2025-01-01'),first-pd.Timedelta(days=int(rng.integers(0,20))))
        customer_rows.append([cid,registered,rng.choice(['华东','华南','华北','西南','其他']),rng.choice(['普通','银卡','金卡'],p=[.72,.20,.08])])
    customers=pd.DataFrame(customer_rows,columns=['customer_id','registered_at','region','membership'])
    orders=[];items=[];line_no=0
    for k,s in enumerate(sessions.loc[placed].itertuples(index=False),start=1):
        oid=f'O{k:06}';cancelled=bool(rng.random()<.10)
        count=int(rng.choice([1,2,3],p=[.57,.32,.11]));selected=[int(rng.integers(24))]
        if count>=2:
            second=(selected[0]+6)%24 if rng.random()<.48 else int(rng.integers(24))
            if second not in selected:selected.append(second)
        while len(selected)<count:
            next_p=int(rng.integers(24))
            if next_p not in selected:selected.append(next_p)
        paid_total=refund_total=0
        for pid in selected:
            line_no+=1;p=products.iloc[pid];qty=int(rng.choice([1,2,3],p=[.72,.23,.05]))
            discount=float(rng.choice([0,.05,.10,.15],p=[.55,.22,.17,.06]))
            gross=int(p.list_price_cents)*qty;discount_cents=int(round(gross*discount));paid=0 if cancelled else gross-discount_cents
            refunded_qty=0;refund_date=pd.NaT
            candidate=s.session_date.normalize()+pd.Timedelta(days=int(rng.integers(5,22)))
            if not cancelled and candidate<AS_OF and rng.random()<.085:
                refunded_qty=int(rng.integers(1,qty+1));refund_date=candidate
            refund=paid*refunded_qty//qty
            items.append([f'L{line_no:06}',oid,p.product_id,qty,gross,discount_cents,paid,refunded_qty,refund,refund_date])
            paid_total+=paid;refund_total+=refund
        status='cancelled' if cancelled else ('refunded' if paid_total==refund_total and refund_total>0 else 'paid')
        orders.append([oid,s.session_id,s.customer_id,s.session_date,s.channel,s.device,status,paid_total,refund_total,0 if cancelled else 800])
    orders=pd.DataFrame(orders,columns=['order_id','session_id','customer_id','order_date','channel','device','status','paid_total_cents','refund_total_cents','fulfilment_fee_cents'])
    items=pd.DataFrame(items,columns=['line_id','order_id','product_id','quantity','gross_cents','discount_cents','paid_cents','refunded_qty','refund_cents','refund_date'])
    sessions=sessions.merge(orders[['session_id','paid_total_cents']],on='session_id',how='left',validate='one_to_one')
    sessions['paid_order']=sessions['paid_total_cents'].fillna(0).gt(0).astype(int)
    sessions=sessions.drop(columns='paid_total_cents')
    # 营销费用按日、渠道记录。自然渠道为0，ROAS因此未定义，不能画成无穷大。
    daily_sessions=sessions.assign(date=sessions.session_date.dt.normalize()).groupby(['date','channel']).size()
    marketing=[]
    for day in days:
        for ch in channels:
            visits=int(daily_sessions.get((day,ch),0));cpv={'organic':0,'paid_search':90,'social':65,'affiliate':45}[ch]
            spend=int(round(visits*cpv*rng.uniform(.8,1.2)))
            marketing.append([day,ch,spend])
    marketing=pd.DataFrame(marketing,columns=['marketing_date','channel','spend_cents'])
    paid_items=items.merge(orders[['order_id','order_date','status']],on='order_id',validate='many_to_one')
    paid_items=paid_items.loc[paid_items.status.ne('cancelled')].copy()
    shipped=paid_items.assign(date=paid_items.order_date.dt.normalize()).groupby(['date','product_id']).quantity.sum()
    restock=paid_items.loc[paid_items.refunded_qty.gt(0)].groupby(['refund_date','product_id']).refunded_qty.sum()
    inventory=[]
    for product in products.itertuples(index=False):
        opening=int(rng.integers(120,181))
        for day in days:
            sold=int(shipped.get((day,product.product_id),0));returned=int(restock.get((day,product.product_id),0))
            inbound=max(0,240-opening-returned) if opening+returned-sold<80 else 0
            closing=opening+inbound+returned-sold
            assert closing>=0
            inventory.append([day,product.product_id,opening,inbound,sold,returned,closing]);opening=closing
    inventory=pd.DataFrame(inventory,columns=['inventory_date','product_id','opening_qty','inbound_qty','shipped_qty','restock_qty','closing_qty'])
    # 独立的用户级随机试验，和访问/订单表不能直接相加；每位用户一行。
    size=8000;variant=rng.choice(['A','B'],size);p=np.where(variant=='A',.10,.112);converted=rng.random(size)<p
    experiment=pd.DataFrame({'visitor_id':[f'AB{i:05}' for i in range(1,size+1)],'variant':variant,
        'converted':converted.astype(int),'revenue_cents':np.where(converted,rng.integers(3000,18000,size),0)})
    positives=['包装完好，发货快','质量不错，性价比高','使用方便，服务满意','价格合理，体验不错']
    negatives=['物流慢，希望改进','质量一般，包装破损','客服回复慢，不太满意','价格偏高，体验一般']
    reviews=[]
    paid_lines=paid_items.loc[paid_items.refunded_qty.eq(0)]
    for i in range(800):
        row=paid_lines.iloc[int(rng.integers(len(paid_lines)))];stars=int(rng.choice([1,2,3,4,5],p=[.05,.08,.17,.33,.37]))
        content=rng.choice(positives if stars>=4 else negatives)
        reviews.append([f'R{i+1:04}',row.order_id,row.product_id,stars,content])
    reviews=pd.DataFrame(reviews,columns=['review_id','order_id','product_id','rating','review_text'])
    dirty=orders.copy();dirty['order_date']=dirty.order_date.astype(str)
    dirty['paid_yuan_raw']=dirty.paid_total_cents.map(lambda x:f'¥{x/100:,.2f}')
    dirty.loc[dirty.index[:6],'order_date']='错误日期'
    dirty.loc[dirty.index[6:10],'paid_yuan_raw']='待核对'
    dirty.loc[dirty.index[10:12],'paid_yuan_raw']='-100.00'
    dirty['customer_id']=' '+dirty.customer_id+' '
    dirty['channel']=' '+dirty.channel.str.upper()+' '
    dirty.loc[dirty.index[20:30],'channel']=None
    dirty=pd.concat([dirty,dirty.iloc[50:65]],ignore_index=True)
    tables={'customers':customers,'products':products,'sessions':sessions,'orders':orders,'order_items':items,
        'marketing':marketing,'inventory':inventory,'experiment':experiment,'reviews':reviews,'orders_dirty':dirty}
    for name,frame in tables.items():frame.to_csv(DATA/f'{name}.csv',index=False,encoding='utf-8-sig')
    metadata={'synthetic_only':True,'seed':SEED,'order_window':['2025-01-01','2025-12-31'],
        'snapshot_exclusive':'2026-01-01','money_unit':'CNY cents, integer','rows':{k:len(v) for k,v in tables.items()},
        'assumptions':['All customers register within the observation year; no prior transaction history is omitted.',
        'At most one order per session; visits are sessions, not distinct people.',
        'Teaching management report on payment/order-day basis, not statutory revenue recognition.',
        'Refunds are observed only before snapshot; returned goods fully resalable at original cost.',
        'Inventory shipments are simplified to paid-order day; replenishment is unconstrained.',
        '3% platform fee on net merchandise sales; refundable; 800-cent fulfilment charge per paid order remains after return.',
        'Merchandise revenue excludes shipping, tax and overhead; contribution excludes marketing until explicitly subtracted.',
        'Marketing is session-entry attribution, not causal incremental return.',
        'Reviews are fictional rule-based examples; experiment is independent user-level synthetic randomisation.'],
        'experiment_generation_probabilities':{'A':.10,'B':.112},
        'dirty_orders':{'duplicate_order_ids_added':15,'bad_date_rows':6,'bad_amount_rows':6,'missing_channel_rows':10}}
    (DATA/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf8')
    print('模拟数据生成完成：',metadata['rows'])
    return metadata

if __name__=='__main__':generate()
