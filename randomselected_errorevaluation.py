#此文件用来检测随机选择的线时相对强度的误差
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import glob
import os
from itertools import combinations
from error_evaluation import read_csv_with_fallback


kB=8.617330350e-5 #eV/K


#此处设计选择逻辑
def iter_all_line_combinations(wl, A, E, g, min_lines=2, max_lines=None):
    """遍历所有谱线组合（默认至少 2 条）。

    产出:
        idx, wl_sub, A_sub, E_sub, g_sub
    其中 idx 是当前组合对应的原始下标。
    """
    total = len(E)
    if not (len(wl) == len(A) == len(E) == len(g)):
        raise ValueError('wl, A, E, g 长度不一致。')

    min_n = int(min_lines)
    if min_n < 1:
        raise ValueError('min_lines 必须 >= 1。')

    if max_lines is None:
        max_n = total
    else:
        max_n = int(max_lines)

    if max_n < min_n:
        raise ValueError('max_lines 不能小于 min_lines。')

    max_n = min(max_n, total)
    if min_n > total:
        return

    for n in range(min_n, max_n + 1):
        for idx_tuple in combinations(range(total), n):
            idx = np.array(idx_tuple, dtype=int)
            yield idx, wl[idx], A[idx], E[idx], g[idx]
#计算相对强度
def U_Calculate(g,A,E,T):
    if T <= 0:
        U = np.zeros(len(g), dtype=float)
        return U, 0.0
    U = g * np.exp(-E / (kB * T))
    U = np.where(np.isfinite(U), U, 0.0)
    return U, float(np.sum(U))
def rel_intensity(wl,A,E,g,T):
    _, U_T_sum = U_Calculate(g, A, E, T)
    rel_intensity = np.zeros(len(wl), dtype=float)


    if T <= 0:
        return rel_intensity

    # 仅在分母有效时计算，避免除零和无效值告警
    denominator = U_T_sum * wl
    valid = np.isfinite(denominator) & (np.abs(denominator) > 1e-30)
    if np.any(valid):
        numerator = A * g * np.exp(-E / (kB * T))
        valid = valid & np.isfinite(numerator)
        rel_intensity[valid] = numerator / denominator[valid]

    return rel_intensity/sum(rel_intensity)  # 归一化处理，确保总和为1



#数据导入
# file_path = r'D:\LIBS\RREdetectation\Rareearth_pt3\CeII.csv'
# df_raw = read_csv_with_fallback(file_path, header=0)

file_path= r'D:\LIBS\RREdetectation\Rareearth_pt3'
I_file_list = glob.glob(os.path.join(file_path, "*.csv"))
I_elements_list = [os.path.splitext(os.path.basename(f))[0] for f in I_file_list]
I_elements_list = [name for name in I_elements_list if name.upper().endswith('II')]
output_dir = r'D:\LIBS\RREdetectation\Randomselected_delta_5K-20K'
os.makedirs(output_dir, exist_ok=True)
print("找到以下元素文件：", I_elements_list)
for elem_name in I_elements_list:
    target_path=os.path.join(file_path, f"{elem_name}.csv")
    print (f"正在处理文件: {target_path}")
    df_raw = read_csv_with_fallback(target_path, header=0)

    #数据处理
    df = df_raw.copy()
    df = df.iloc[1::2].copy()
    # 第9列为 N 时，仅在第10列非空时保留；第10列为空则剔除
    if df.shape[1] >= 9:
        col9 = df.iloc[:, 8].astype(str).str.strip().str.upper()
        col9_is_n = col9 == 'N'

        if df.shape[1] >= 10:
            col10 = df.iloc[:, 9]
            col10_not_empty = col10.notna() & (col10.astype(str).str.strip() != '')
        else:
            col10_not_empty = pd.Series(False, index=df.index)

        keep_mask = (~col9_is_n) | col10_not_empty
        df = df.loc[keep_mask].reset_index(drop=True)

    # 只保留计算所需列，并将空值/非法值统一转为 NaN
    needed_col_idx = [1, 2, 3, 7]
    needed_cols = [df.columns[i] for i in needed_col_idx]
    for col in needed_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 去除关键列中包含 NaN 或无穷值的行
    df[needed_cols] = df[needed_cols].mask(~np.isfinite(df[needed_cols]), np.nan)
    df = df.dropna(subset=needed_cols).reset_index(drop=True)

    wl = df.iloc[:, 1].to_numpy(dtype=float)
    A  = df.iloc[:, 2].to_numpy(dtype=float)
    E  = df.iloc[:, 3].to_numpy(dtype=float)
    g  = df.iloc[:, 7].to_numpy(dtype=float)

    wl = wl * 0.1              
    E  = E  * 1.2398e-4  

    #遍历所有随机组合的相对强度变化量
    combinations_list = list(iter_all_line_combinations(wl, A, E, g, min_lines=2, max_lines=10))
    records = []
    for idx, wl_sub, A_sub, E_sub, g_sub in combinations_list:

        delta_p = rel_intensity(wl_sub, A_sub, E_sub, g_sub, T=20000) - rel_intensity(wl_sub, A_sub, E_sub, g_sub, T=5000)
        records.append({
            'idx': idx.tolist(),
            'n_lines': int(len(idx)),
            'wl': wl_sub.tolist(),
            'A': A_sub.tolist(),
            'E': E_sub.tolist(),
            'g': g_sub.tolist(),
            'delta_p': delta_p.tolist(),
            'max_abs_delta_p': float(np.max(np.abs(delta_p))),
        })

    result_df = pd.DataFrame(records)


    # # 若需保存可取消注释
    output_csv = os.path.join(output_dir, elem_name + '.csv')
    result_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f'结果已保存到: {output_csv}')


#保存
#最终保存为csv，包含组合的下标、对应的 wl, A, E, g 数组，以及误差评估结果


