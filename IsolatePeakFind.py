#该程序用于寻找元素的孤立峰
import pandas as pd
import glob
import os
import numpy as np
import matplotlib.pyplot as plt 
from Elements_Combfact import elements_database,elements_database_pt2
from Wavelet_peakfinding import find_peaks_ridge,peak_correction,wavelet_peak_detection #寻峰

"""
稀土元素孤立峰寻找：
1.对全稀土元素光谱进行寻峰
2.对每个稀土元素光谱进行寻峰
3.对比两者峰值位置，寻找孤立峰
"""

def IsolatePeakFind(folder_path):
    #读取稀土元素库
    file_list = glob.glob(os.path.join(folder_path, "*.csv"))
    # elements_list = [os.path.splitext(os.path.basename(f))[0] for f in file_list]
    elements,elements_list=elements_database_pt2(folder_path,T=3000) #元素库制作

    

    #全稀土元素光谱数据读取
    data=pd.read_csv(r'D:\LIBS\ElementDetectation\11.10\Rareearth\Spectrum\All.csv',header=0,skipinitialspace=True)#待测光谱路径
    data = data.fillna(0).to_numpy()
    data = np.nan_to_num(data, nan=0.0)
    signal=data[:,1]
    x= data[:, 0]
    #全稀土元素光谱寻峰
    true_peak_idx, peak_wl, peak_int = wavelet_peak_detection(signal,x,wavelet='mexh', scales=np.arange(1, 11), 
                               neighbor=4, min_length=3, coeffi_threshold=1000, window=5)#峰值校正
    

    #元素孤立峰寻找
    for element_name in elements_list:
        element_wl = elements[element_name]['data'][:, 0]
        element_ri = elements[element_name]['data'][:, 1]/np.sum(elements[element_name]['data'][:, 1]) #相对强度归一化
        #单个元素光谱寻峰
        min_distances = []
        for wl in element_wl:
            distances = np.abs(peak_wl - wl)
            min_dist = np.min(distances) if len(distances) > 0 else np.inf
            min_distances.append(min_dist)

        #按距离从小到大输出（元素内部）
        for min_dist, wl, ri in sorted(zip(min_distances, element_wl, element_ri), key=lambda r: r[0]):
            print(f"元素: {element_name}, 波长: {wl:.2f} nm, 相对强度: {ri:.4f}, 最小距离: {min_dist:.2f} nm")
            


folder_path =r'D:\LIBS\ElementDetectation\11.10\Rareearth' #稀土元素光谱路径
IsolatePeakFind(folder_path)
