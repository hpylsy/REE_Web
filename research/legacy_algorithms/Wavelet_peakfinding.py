#小波变换寻峰算法
#效果：输入光谱数据，输出峰值位置和大小，无论展宽。
#寻峰方式：脊线寻峰
#待解决问题：1、参数设置（尺度，领域半径，最小脊线长度） 2、脊线校正未作 3、处理nan值


import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import pywt



data=pd.read_csv(r'D:\LIBS\RREdetectation\RREs\03116_95.csv',header=0,skipinitialspace=True)
data = data.fillna(0).to_numpy()
data = np.nan_to_num(data, nan=0.0)

x=data[:,0]
x = np.array([float(str(val).replace('\xa0', '').strip()) for val in x])
intensity_sum=data[:,1]
signal=data[:,1]
intensity_ion=data[:,3]


# ====== 2. 定义小波参数 ======
wavelet = 'mexh'  # 小波函数
scales = np.arange(1, 11)  # 尺度范围 (1=窄峰, 大=宽峰)
coefficients, frequencies = pywt.cwt(signal, scales, wavelet)
coefficients.shape = (len(scales), len(signal))


#寻峰策略2：脊线寻峰
#策略：从最大尺度的第一个极大值点开始描点
#signal为原始信号，coefficients为小波系数，neighbor为邻域半径，min_length为最小脊线长度
def find_peaks_ridge(signal,coefficients,neighbor=4,min_length=3,coeffi_threshold=1000): 
    n_scales, n_points = coefficients.shape
    maxindex=np.zeros(coefficients.shape)

    #极大值搜寻
    for i in range(len(coefficients)-1,-1,-1):
        for j in range(1,len(signal)-1):
            if coefficients[i,j]>coefficients[i,j+1] and coefficients[i,j]>coefficients[i,j-1]: 
                maxindex[i,j]=1  
                # print(i,j)
    # print("Already got the maxindex")

    #脊线搜寻策略
    ridges=[] 
    for j in np.where(maxindex[-1] == 1)[0]:  # 找最大尺度的极大值点
            ridge = [[n_scales-1, j]]  # 新开一条脊线，从最后一行开始
            prev_pos = j
            # 逐行往上追踪
            for i in range(n_scales-2, -1, -1):
                # 在 ±neighbor 范围内寻找极大值
                candidates = [k for k in range(max(1, prev_pos-neighbor), min(n_points-1, prev_pos+neighbor+1)) if maxindex[i, k] == 1]
                if candidates:
                    # 如果有多个候选，可以选最接近的
                    next_pos = min(candidates, key=lambda x: abs(x-prev_pos))
                    ridge.append([i, next_pos])
                    prev_pos = next_pos
                else:
                    # ridge.append([i, np.inf])  # 没找到
                    break

            ridges.append(ridge)
           

    #脊线初步筛选（能量，长度）
    filtered_ridges = []
    for ridge in ridges:
        valid_points = sum(1 for _, pos in ridge if pos != np.inf)
        if valid_points >= min_length: #脊线长度筛选
            ridge_coeffs=[]
            for scale_idx,pos_idx in ridge:
                ridge_coeffs.append(coefficients[scale_idx, pos_idx])
                if np.max(ridge_coeffs) > coeffi_threshold: #脊线能量筛选
                    filtered_ridges.append(ridge)

    # #初步峰位提取
    # peaks = []
    # for ridge in filtered_ridges:
    #     min_scale_pos = min(ridge, key=lambda x: x[0])  # 最小尺度的位置
    #     peaks.append((ridge, min_scale_pos[1], min_scale_pos[0])) # (脊线, 位置, 尺度)

    # #脊线校正
    # corrected_peaks = []
    # peaks_sorted = sorted(peaks, key=lambda x: x[1])  # 按位置排序
    
    # for i, (ridge, pos, scale) in enumerate(peaks_sorted):#(元素和索引)
    #     prev_pos = peaks_sorted[i-1][1] if i > 0 else None
    #     next_pos = peaks_sorted[i+1][1] if i < len(peaks_sorted)-1 else None
    #     #判断复合脊线：相邻峰值间距大于2倍尺度视为复合脊线
    #     is_composite = False
    #     if prev_pos is not None and abs(pos - prev_pos) > scale*2:
    #         is_composite = True
    #     if next_pos is not None and abs(pos - next_pos) > scale*2:
    #         is_composite = True

    #     if is_composite:
    #         # 从大尺度到小尺度逐步截断
    #         for (s, p) in sorted(ridge, key=lambda x: -x[0]):  
    #             if prev_pos is not None and abs(p - prev_pos) <= s*2:
    #                 corrected_peaks.append(p)
    #                 break
    #             elif next_pos is not None and abs(p - next_pos) <= s*2:
    #                 corrected_peaks.append(p)
    #                 break
    #     else:
    #         corrected_peaks.append(pos)

    # # 去重
    # corrected_peaks = sorted(list(set(corrected_peaks)))
    # return corrected_peaks
    return  filtered_ridges

#脊线峰值校正
def peak_correction(ridges_found, wl, intensity, window=5):
    peak_ridgefound = []
    true_peaks_idx = []

    for ridge in ridges_found:
        # 找脊线中尺度最小的位置
        min_scale_pos = min(ridge, key=lambda x: x[0])
        scale_idx, pos_idx = min_scale_pos

        if np.isfinite(pos_idx):
            pos_idx = int(pos_idx)
            if pos_idx not in peak_ridgefound:  # 去重
                peak_ridgefound.append(pos_idx)

                # 在原始数据中附近寻找极大值
                left = max(0, pos_idx - window)#避免越界
                right = min(len(intensity) - 1, pos_idx + window)#避免越界
                local_region = intensity[left:right+1]

                local_max_idx = np.argmax(local_region) + left
                true_peaks_idx.append(local_max_idx)

    # 转换成波长和强度
    true_peaks_wl = [wl[i] for i in true_peaks_idx]
    true_peaks_int = [intensity[i] for i in true_peaks_idx]

    return true_peaks_idx, true_peaks_wl, true_peaks_int

#小波脊线寻峰+校正整合
def wavelet_peak_detection(signal, wl, wavelet='mexh', scales=np.arange(1, 11), 
                           neighbor=4, min_length=3, coeffi_threshold=1000, window=5):

    # ====== 1. 小波变换 ======
    coefficients, frequencies = pywt.cwt(signal, scales, wavelet)
    n_scales, n_points = coefficients.shape
    
    # ====== 2. 极大值点搜索 ======
    maxindex = np.zeros_like(coefficients, dtype=int)
    for i in range(n_scales-1, -1, -1):
        for j in range(1, n_points-1):
            if coefficients[i, j] > coefficients[i, j+1] and coefficients[i, j] > coefficients[i, j-1]:
                maxindex[i, j] = 1
    
    # ====== 3. 脊线跟踪 ======
    ridges = []
    for j in np.where(maxindex[-1] == 1)[0]:  # 从最大尺度的极大值点出发
        ridge = [[n_scales-1, j]]
        prev_pos = j
        for i in range(n_scales-2, -1, -1):
            candidates = [k for k in range(max(1, prev_pos-neighbor),
                                           min(n_points-1, prev_pos+neighbor+1))
                          if maxindex[i, k] == 1]
            if candidates:
                next_pos = min(candidates, key=lambda x: abs(x-prev_pos))
                ridge.append([i, next_pos])
                prev_pos = next_pos
            else:
                break
        ridges.append(ridge)
    
    # ====== 4. 脊线筛选（长度+能量） ======
    filtered_ridges = []
    for ridge in ridges:
        valid_points = sum(1 for _, pos in ridge if pos != np.inf)
        if valid_points >= min_length:
            ridge_coeffs = [coefficients[s, p] for s, p in ridge]
            if np.max(ridge_coeffs) > coeffi_threshold:
                filtered_ridges.append(ridge)
    
    # ====== 5. 峰值矫正 ======
    peak_ridgefound = []
    true_peaks_idx = []
    for ridge in filtered_ridges:
        min_scale_pos = min(ridge, key=lambda x: x[0])  # 最小尺度点
        scale_idx, pos_idx = min_scale_pos
        if np.isfinite(pos_idx):
            pos_idx = int(pos_idx)
            if pos_idx not in peak_ridgefound:
                peak_ridgefound.append(pos_idx)
                left = max(0, pos_idx - window)
                right = min(len(signal)-1, pos_idx + window)
                local_region = signal[left:right+1]
                local_max_idx = np.argmax(local_region) + left
                true_peaks_idx.append(local_max_idx)
    
    # ====== 6. 转换成波长和强度 ======
    true_peaks_wl = [wl[i] for i in true_peaks_idx]
    true_peaks_int = [signal[i] for i in true_peaks_idx]
    true_peaks_wl=np.array(true_peaks_wl)
    return true_peaks_idx, true_peaks_wl, true_peaks_int

# #调用
# ridges_found=find_peaks_ridge(signal,coefficients,neighbor=3,min_length=3,coeffi_threshold=100) #小波脊线寻峰
# #后续对接
# #理想输出peak_ridgefound：峰值位置，峰值大小
# peak_ridgefound=[]
# for ridge in ridges_found:
#     min_scale_pos=min(ridge,key=lambda x:x[0])
#     scale_idx,pos_idx=min_scale_pos
#     if np.isfinite(pos_idx) and int(pos_idx) not in peak_ridgefound:  # 去重
#         peak_ridgefound.append(int(pos_idx))
# # print(peak_ridgefound)


# # true_peak_idx, true_peak_wl, true_peak_int = peak_correction(ridges_found, x, signal, window=5) 


# true_peak_idx, true_peak_wl, true_peak_int = wavelet_peak_detection(signal, x, wavelet='mexh', scales=np.arange(1, 11), 
#                                                                    neighbor=3, min_length=3, coeffi_threshold=100, window=5)
# print(len(true_peak_wl))
# #脊线寻峰结果显示
# fig, (ax1, ax2, ax3) = plt.subplots(3, 1, sharex=True, figsize=(8, 6))

# # 原始信号1
# ax1.plot(x, signal,color='black',lw=1, label="Signal")
# ax1.scatter(x[true_peak_idx], signal[true_peak_idx], color='red', s=5)
# ax1.legend()

# # 脊线寻峰结果2
# for ridge in ridges_found:
#     scales = [p[0] for p in ridge]
#     positions = [p[1] for p in ridge]
#     positions = np.array(positions, dtype=float)
#     scales = np.array(scales, dtype=float)
#     mask = np.isfinite(positions)
#     positions = positions[mask].astype(int)
#     scales = scales[mask]
#     ax2.scatter(x[positions], scales, color='red', s=2)
# ax2.set_ylabel("Scale")
# ax2.invert_yaxis()

# # 小波系数图3
# ax3.imshow(coefficients,
#            extent=[x.min(), x.max(), scales.max(), scales.min()],
#            cmap='jet', aspect='auto')
# ax3.set_xlabel("x")
# ax3.set_ylabel("Scale")
# ax3.set_title("CWT Coefficients")

# plt.tight_layout()
# plt.show()
