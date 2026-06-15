#本文件用于验证谱线选择Branch
#SpectalConflictFinder.py 顾名思义，就是用来找稀土元素离子线与岩石基体元素之间的冲突的
#Already done
import numpy as np
import pandas as pd
import glob
import os
import re
import pywt
import matplotlib.pyplot as plt
from Wavelet_peakfinding import find_peaks_ridge,wavelet_peak_detection

THRESHOLD = 0.15  # nm distance allowed between catalog line and detected peak

#Ne=(FWHM/gamma)*sqrt(ln(2)/pi)*1e16

folder_path = r'D:\LIBS\RREdetectation\Rareearth' #元素谱线库的路径
folder_path2=r'D:\LIBS\RREdetectation\PureMainElems' #冲突谱线的输出路径

file_list = glob.glob(os.path.join(folder_path, "*II.csv")) # 只处理离子态谱线文�?
file_list2 = glob.glob(os.path.join(folder_path2, "*.csv")) # 只处理离子态谱线文档
elements_list = [os.path.splitext(os.path.basename(f))[0] for f in file_list]
PureElem_list=[os.path.splitext(os.path.basename(f))[0] for f in file_list2]
PureElem_base = [re.sub(r"\d+$", "", name) for name in PureElem_list] #主元素
elements = {}
conflicts = []  # store near-peak matches for later use

for element_name in elements_list: 
    #数据预处理
    file_path = os.path.join(folder_path, element_name + ".csv")
    df = pd.read_csv(file_path, header=1, encoding="gbk")
    df = df.iloc[1::2].copy()
    wl=df.iloc[:,1]
    #仅检测未启用的（N）的谱线
    if df.shape[1] > 8:
        enable_flag = df.iloc[:, 8]
        enable_mask = enable_flag.astype(str).str.strip().str.upper().eq("N")
    else:
        enable_mask = pd.Series(False, index=df.index)

    wl = pd.to_numeric(wl, errors="coerce")
    wl = wl * 0.1 
    valid_mask = (enable_mask &np.isfinite(wl))
    wl = wl[valid_mask]
    band_mask = (wl >= 200) & (wl <= 900)
    wl = wl[band_mask]
    wl = wl.to_numpy(dtype=float)
    elements[element_name] = wl #谱线库创建完成


    #遍历岩石基体元素
    for PureElem_name in PureElem_base:
        PureElem_path = os.path.join(folder_path2, PureElem_name + "100.csv")
        df2 = pd.read_csv(PureElem_path, header=0, encoding="gbk")
        wl_Pure=df2.iloc[:,0]
        wl_Pure = pd.to_numeric(wl_Pure, errors="coerce")
        int_Pure=df2.iloc[:,1]
        int_Pure = pd.to_numeric(int_Pure, errors="coerce")
        true_peak_idx, peak_wl, peak_int = wavelet_peak_detection(int_Pure,wl_Pure,wavelet='mexh', scales=np.arange(1, 11), 
                               neighbor=4, min_length=3, coeffi_threshold=700, window=5)#峰值校正
        

        # 找到所有距离任意参考谱线小于 THRESHOLD 的峰值组合（不是只取最近一条）
        if peak_wl.size and wl.size:
            diff = np.abs(peak_wl[:, None] - wl[None, :])
            peak_idx, ref_idx = np.where(diff < THRESHOLD)
            for i, j in zip(peak_idx, ref_idx):
                conflicts.append({
                    "rareearth": element_name,
                    "pure_elem": PureElem_name,
                    "ref_wl": wl[j],
                    "peak_wl": peak_wl[i],
                    "delta": float(diff[i, j]),
                })
                # print(f"{PureElem_name} 与 {element_name} 存在 {len(peak_idx)} 条距离<{THRESHOLD}nm 的冲突峰")  

# for c in conflicts:
#     print(c)
    # print(c["rareearth"], c["peak_wl"],c["ref_wl"], c["delta"], c["pure_elem"])
    

#遍历稀土元素，更改谱线库中对应元素的谱线文件
for elements_name in elements_list:
    element_conflicts = [c for c in conflicts if c["rareearth"] == elements_name]
    folder_path = r'D:\LIBS\RREdetectation\Rareearth'
    df=pd.read_csv(os.path.join(folder_path, elements_name + ".csv"), header=1, encoding="gbk")


    if element_conflicts:
        conf_df = pd.DataFrame(element_conflicts)
        cols = ["peak_wl", "ref_wl", "delta", "pure_elem"]
        # print(conf_df["ref_wl"])
        # print(conf_df["pure_elem"])
        # 准备波长列：第1列转换为 nm（*0.1），并保证存在写入列（末尾新增）
        df_wl = pd.to_numeric(df.iloc[:, 1], errors="coerce") * 0.1
        if df.shape[1] <= 9:
            df.insert(loc=df.shape[1], column="conflict_elem", value=np.nan) #新建列
        target_col = df.columns[-1]  # 最后一列列名
        # 确保目标列可以写入字符串，否则 pandas 会提示类型不兼容
        df[target_col] = df[target_col].astype(object)


        # 将冲突峰值对应的基体元素写回谱线表
        for _, row in conf_df.iterrows():
            peak_wl = float(row["ref_wl"])
            pure_elem = row["pure_elem"]
            # print(peak_wl, pure_elem)
            # 按波长精确匹配，无需容差
            tol=5e-2
            match_mask = np.isclose(df_wl, peak_wl, atol=tol, equal_nan=False)
            if match_mask.any():
                df.loc[match_mask, target_col] = pure_elem

    # 无论是否有冲突，直接覆盖原目录中的文件
    # df.to_csv(os.path.join(folder_path, elements_name + ".csv"), index=False, encoding="gbk")
    #在新的文件夹中保存
    output_path = r'D:\LIBS\RREdetectation\Rareearth_pt3' #冲突谱线的输出路径
    os.makedirs(output_path, exist_ok=True)
    df.to_csv(os.path.join(output_path, elements_name + ".csv"), index=False, encoding="gbk")
   


