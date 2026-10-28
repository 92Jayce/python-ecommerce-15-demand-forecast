"""第15讲 需求预测与时间顺序回测
业务问题：模型能否战胜“下周同一天和上周一样”的基线？
全部使用模拟教学数据。"""
from pathlib import Path
import sys
if "__file__" in globals():
    COURSE_ROOT = Path(__file__).resolve().parents[1]
else:
    COURSE_ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "course_common.py").exists())
if str(COURSE_ROOT) not in sys.path:
    sys.path.insert(0, str(COURSE_ROOT))
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from course_common import (ROOT, DATA, AS_OF, BLUE, TEAL, ORANGE, load_tables,
    build_facts, positive_orders, rfm_table, safe_divide, outdir, save_table, save_figure, show)

# %% 只用预测时点之前可得的信息构造特征
inv=load_tables()['inventory'];y=inv.groupby('inventory_date').shipped_qty.sum().reindex(pd.date_range('2025-01-01','2025-12-31'),fill_value=0).astype(float)
frame=pd.DataFrame({'y':y,'lag1':y.shift(1),'lag7':y.shift(7),'lag14':y.shift(14),
    'past7_mean':y.shift(1).rolling(7).mean(),
    'weekday_sin':np.sin(2*np.pi*y.index.dayofweek/7),'weekday_cos':np.cos(2*np.pi*y.index.dayofweek/7)})
frame=frame.dropna();train=frame.iloc[:-28];test=frame.iloc[-28:]
assert train.index.max()<test.index.min()
features=['lag1','lag7','lag14','past7_mean','weekday_sin','weekday_cos']
X=np.column_stack([np.ones(len(train)),train[features].to_numpy()]);X_test=np.column_stack([np.ones(len(test)),test[features].to_numpy()])
coef=np.linalg.lstsq(X,train.y.to_numpy(),rcond=None)[0]
prediction=np.maximum(0,X_test@coef)
pred=test[['y','lag7','past7_mean']].copy();pred['linear_model']=prediction

# %% 固定模型的连续单步回测：每一天允许使用刚过去各天的真实需求
rows=[]
for model in ['lag7','past7_mean','linear_model']:
    err=pred[model]-pred.y
    rows.append({'model':model,'MAE':np.abs(err).mean(),'RMSE':np.sqrt(np.mean(err**2)),
        'WAPE':np.abs(err).sum()/pred.y.abs().sum()})
metrics=pd.DataFrame(rows);show(metrics);save_table(metrics,15,'forecast_metrics');save_table(pred.reset_index(),15,'rolling_one_step_predictions')
fig,ax=plt.subplots(figsize=(9,4));ax.plot(pred.index,pred.y,label='Observed',color='#263F50')
ax.plot(pred.index,pred.lag7,label='Seasonal naive',color=ORANGE,ls='--');ax.plot(pred.index,pred.linear_model,label='Linear model',color=BLUE)
ax.set(title='Fixed-model rolling one-day-ahead backtest',ylabel='Units');ax.legend(fontsize=8);save_figure(fig,15,'forecast_backtest')
print('这不是一次性预测未来28天：测试期后段使用已发生的前一天真实值。未来多步预测需要递归或专门模型。')
