#该文件是稀土元素检测的核心文件，包含了元素匹配、玻尔兹曼图拟合、置信度计算等关键函数


import numpy as np
import pandas as pd
import glob
import os
import pywt
import matplotlib.pyplot as plt
import warnings
from collections import defaultdict
from Wavelet_peakfinding import find_peaks_ridge,peak_correction,wavelet_peak_detection #寻峰
from Elements_Combfact import elements_database, elements_database_pt2,elements_database_lineswitch#元素库制作
from scipy.optimize import linear_sum_assignment #匈牙利算法
from RandSpec_PerformanceOP import RandSepc_PerforOP #随机光谱性能评估
from error_evaluation import U_Calculate, rel_intensity
from MultiPeakfit.Gaussfit import CWTPeakFWHMEstimator,GaussMultiPeakFitter


#终端颜色设置
RESET = "\033[0m"
BLUE = "\033[34m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"


def _enable_windows_ansi():
    if os.name != "nt":
        return True
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        if handle == 0 or handle == -1:
            return False

        mode = wintypes.DWORD()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)) == 0:
            return False

        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        if (mode.value & ENABLE_VIRTUAL_TERMINAL_PROCESSING) == 0:
            if kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING) == 0:
                return False
        return True
    except Exception:
        return False


COLOR_ENABLED = (
    os.getenv("NO_COLOR") is None
    and (
        bool(os.getenv("FORCE_COLOR"))
        or
        os.name != "nt"
        or _enable_windows_ansi()
        or bool(os.getenv("WT_SESSION"))
        or bool(os.getenv("ANSICON"))
        or bool(os.getenv("TERM"))
    )
)


def color_text(text, color):
    if not COLOR_ENABLED:
        return text
    return f"{color}{text}{RESET}"


#-----预备-----
#参数设置

kB=8.617330350e-5 #eV/K

def _safe_linear_polyfit(Ev, yv):
    Ev = np.asarray(Ev, dtype=float)
    yv = np.asarray(yv, dtype=float)

    if Ev.size < 2 or yv.size < 2 or Ev.size != yv.size:
        return None
    if not (np.isfinite(Ev).all() and np.isfinite(yv).all()):
        return None
    if np.unique(Ev).size < 2:
        return None

    spread = np.ptp(Ev)
    scale = max(1.0, float(np.max(np.abs(Ev))))
    if spread <= np.finfo(float).eps * scale:
        return None

    try:
        with warnings.catch_warnings():
            if hasattr(np, "RankWarning"):
                warnings.simplefilter("error", np.RankWarning)
            warnings.filterwarnings(
                "error",
                message="invalid value encountered in divide",
                category=RuntimeWarning,
            )
            return np.polyfit(Ev, yv, 1)
    except (np.linalg.LinAlgError, RuntimeWarning):
        return None


#----必备函数定义----
###玻尔兹曼图拟合
def Boltzmann_fit(I, wl, A, g, E):
    # Filter invalid / non-positive values to avoid log and fit failures
    mask = (
        np.isfinite(I) & np.isfinite(wl) & np.isfinite(A) & np.isfinite(g) & np.isfinite(E) &
        (I > 0) & (wl > 0) & (A > 0) & (g > 0)
    )
    I = I[mask]
    wl = wl[mask]
    A = A[mask]
    g = g[mask]
    E = E[mask]

    if len(E) < 2:
        return 0, 0, 0, 0, np.array([])

    y = np.log(I*wl / (g * A))

    fit = _safe_linear_polyfit(E, y)
    if fit is None:
        return 0, 0, 0, 0, y
    slope, intercept = fit

    T = -1 / (slope * kB) if slope != 0 else 0

    y_fit = slope * E + intercept
    ss_res = np.sum((y - y_fit) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    R2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    return slope, intercept, T, R2, y

def Boltzmann_fit_iterative(I, wl, A, g, E,R2_threshold=1e-1,R2_start_threshold=0.97,max_iter=5,verbose=False):
    """Iterative Boltzmann fit with outlier removal."""
    I = np.array(I, float)
    wl = np.array(wl, float)
    A = np.array(A, float)
    g = np.array(g, float)
    E = np.array(E, float)

    mask = (
        np.isfinite(I) & np.isfinite(wl) & np.isfinite(A) & np.isfinite(g) & np.isfinite(E) &
        (I > 0) & (wl > 0) & (A > 0) & (g > 0)
    )
    I, wl, A, g, E = I[mask], wl[mask], A[mask], g[mask], E[mask]

    if len(E) < 2:
        return 0, 0, 0, 0, np.array([]), E, wl, I, A, g

    def _fit_once(Ev, yv):
        return _safe_linear_polyfit(Ev, yv)

    y = np.log(I * wl / (g * A))
    fit = _fit_once(E, y)
    if fit is None:
        return 0, 0, 0, 0, y, E, wl, I, A, g
    slope, intercept = fit
    y_pred = slope * E + intercept

    ss_res = np.sum((y - y_pred)**2)
    ss_tot = np.sum((y - np.mean(y))**2)
    R2_init = 1 - ss_res / ss_tot if ss_tot != 0 else 0

    if verbose:
        print(f"[Init] R2={R2_init:.5f}")

    if R2_init >= R2_start_threshold:
        T = -1/(slope*kB) if slope != 0 else 0
        return slope, intercept, T, R2_init, y, E, wl, I, A, g

    R2_prev = R2_init

    for it in range(max_iter):
        if len(E) < 3:
            break

        y = np.log(I * wl / (g * A))
        y_pred = slope * E + intercept
        residuals = y - y_pred
        worst = np.argmax(np.abs(residuals))

        I = np.delete(I, worst)
        wl = np.delete(wl, worst)
        A = np.delete(A, worst)
        g = np.delete(g, worst)
        E = np.delete(E, worst)

        if len(E) < 2:
            break

        y = np.log(I * wl / (g * A))
        fit = _fit_once(E, y)
        if fit is None:
            break
        slope, intercept = fit
        y_pred = slope * E + intercept

        ss_res = np.sum((y - y_pred)**2)
        ss_tot = np.sum((y - np.mean(y))**2)
        R2_new = 1 - ss_res / ss_tot if ss_tot != 0 else 0

        delta_R2 = abs(R2_new - R2_prev)
        if verbose:
            print(f"    R2={R2_new:.5f}, dR2={delta_R2:.6f}")

        if delta_R2 < R2_threshold:
            break

        R2_prev = R2_new

    T = -1/(slope*kB) if slope != 0 else 0
    return slope, intercept, T, R2_prev, np.log(I * wl / (g * A)), E, wl, I, A, g

def Boltzmann_plot(matched_i, matched_wl, element_A, element_E, element_g, element_wl,element_name,mode='normal'):

#参数说明:matched_theo匹配到的理论谱线  matched_exp匹配到的实验谱线  element_A元素的A  element_E元素的E  element_g元素的g  element_wl元素的波长列表  element_name元素名称
#用途说明：检测匹配点并且绘制玻尔兹曼图
    # ====== ② 玻尔兹曼图计算与绘制 ======
    if len(matched_wl) >= 2:  # 至少2个点才能线性拟合
        print(f"\n--- {element_name} 玻尔兹曼图 ---")
        
        # 提取匹配到的谱线参数（与 matched_exp 对应的理论参数）
        matched_wl = np.array([t[0] for t in matched_wl])
        matched_I = np.array([t[1] for t in matched_i])  # 实验强度
        # 从理论库中取对应的 A、E、g
        matched_idx = [np.argmin(np.abs(element_wl - wl)) for wl in matched_wl]
        A_sel = element_A[matched_idx]
        E_sel = element_E[matched_idx]
        g_sel = element_g[matched_idx]


        matched_I = np.array(matched_I, dtype=float)
        A_sel = np.array(A_sel, dtype=float)
        g_sel = np.array(g_sel, dtype=float)
        E_sel = np.array(E_sel, dtype=float)
        if mode=='normal':
        # 玻尔兹曼拟合
            slope, intercept, T_fit,R2, y_full = Boltzmann_fit(matched_I, matched_wl,A_sel, g_sel, E_sel)
            # slope, intercept, T_fit,R2, y_full, y_used = Boltzmann_fit_iterative(matched_I, matched_wl,A_sel, g_sel, E_sel,R2_start_threshold=0.97,max_iter=5,verbose=False)
            # print(f"拟合温度 T = {T_fit:.2f} K, 斜率 = {slope:.3f}")
            plt.figure(figsize=(7, 5))
            plt.scatter(E_sel, y_full, color='tab:red', s=35, label='Used Points')
            plt.plot(E_sel, slope * E_sel + intercept, color='tab:blue', linewidth=2.2,
                     linestyle='--', label=f'Fit T={T_fit:.1f} K, R2={R2:.3f}')

            for spine in plt.gca().spines.values():
                spine.set_linewidth(1.8)
            for label in plt.gca().get_xticklabels():
                label.set_fontweight("semibold")
            for label in plt.gca().get_yticklabels():
                label.set_fontweight("semibold")

            plt.xlabel('E (eV)', fontsize=15, fontweight="semibold")
            plt.ylabel('ln(I / (g·A))', fontsize=15, fontweight="semibold")
            plt.title(f'{element_name} Boltzmann Plot', fontsize=15, fontweight="semibold")

            plt.tick_params(axis='both', which='major', direction='in', top=True, right=True,
                            width=2.0, length=6, labelsize=12)
            plt.tick_params(axis='both', which='minor', direction='in', top=True, right=True,
                            width=2.0, length=6, labelsize=12)
            plt.grid(alpha=0.3)
            plt.legend(loc="upper right", prop={"weight": "semibold", "size": 12}, frameon=False)
            plt.tight_layout()
        if mode=='iterative':
        #绘图
            slope, intercept, T_fit, R2, y_used, E_used, wl_used, I_used, A_used, g_used = \
                Boltzmann_fit_iterative(matched_I, matched_wl, A_sel, g_sel, E_sel,
                                        R2_start_threshold=0.1, max_iter=1, verbose=False)

            plt.figure(figsize=(7, 5))
            plt.scatter(E_used, y_used, color='tab:red', s=35, label='Used Points')
            plt.plot(E_used, slope * E_used + intercept, color='tab:blue', linewidth=2.2,
                     linestyle='--', label=f'Fit T={T_fit:.1f} K, R2={R2:.3f}')

            for spine in plt.gca().spines.values():
                spine.set_linewidth(1.8)
            for label in plt.gca().get_xticklabels():
                label.set_fontweight("semibold")
            for label in plt.gca().get_yticklabels():
                label.set_fontweight("semibold")

            plt.xlabel('E (eV)', fontsize=15, fontweight="semibold")
            plt.ylabel('ln(I / (g·A))', fontsize=15, fontweight="semibold")
            plt.title(f'{element_name} Boltzmann Plot', fontsize=15, fontweight="semibold")

            plt.tick_params(axis='both', which='major', direction='in', top=True, right=True,
                            width=2.0, length=6, labelsize=12)
            plt.tick_params(axis='both', which='minor', direction='in', top=True, right=True,
                            width=2.0, length=6, labelsize=12)
            plt.grid(alpha=0.3)
            plt.legend(loc="upper right", prop={"weight": "semibold", "size": 12}, frameon=False)
            plt.tight_layout()
        
    else:
        print(f"{element_name} 匹配峰数不足，无法绘制玻尔兹曼图。")

###匈牙利算法线匹配策略
def match_spectral_lines(theo_wl, theo_int, exp_wl, exp_int, scope):

    T = len(theo_wl)
    E = len(exp_wl)
    N = max(T, E) 
    cost = np.zeros((N, N), dtype=float)
    BIG = 1e6
    cost[:] = BIG
    for i in range(T):
        for j in range(E):
            cost[i, j] = abs(theo_wl[i] - exp_wl[j])

    #  匈牙利算法
    row_ind, col_ind = linear_sum_assignment(cost)

    theo_vec = []
    exp_vec = []

    matched_theo = []
    matched_exp = []

    for i, j in zip(row_ind, col_ind):

        if i < T:            # 这是一个真实的理论峰
            if j < E:        # 实验峰也是真实的
                diff = abs(theo_wl[i] - exp_wl[j])

                if diff <= scope:
                    # 匹配成功
                    theo_vec.append(theo_int[i])
                    exp_vec.append(exp_int[j])

                    matched_theo.append((theo_wl[i], theo_int[i]))
                    matched_exp.append((exp_wl[j], exp_int[j]))
                else:
                    # 匹配距离太大 → 当作未匹配
                    theo_vec.append(0)
                    exp_vec.append(0)

            else:
                # 实验峰不存在（补的虚拟列）→ 未匹配
                theo_vec.append(0)
                exp_vec.append(0)

    theo_vec = np.array(theo_vec)
    exp_vec = np.array(exp_vec)

    return theo_vec, exp_vec, matched_theo, matched_exp

def match_spectral_lines_weighted(theo_wl, theo_int, exp_wl, exp_int, scope=0.2, max_high_intensity=None, alpha=1.0, beta=1.0):
    """
    匈牙利算法改进：优先匹配高强度实验峰
    
    Parameters:
        theo_wl, theo_int : 理论谱线波长和强度
        exp_wl, exp_int   : 实验谱线波长和强度
        scope             : 匹配容差 (nm)
        max_high_intensity: 限制参与匹配的高强度峰数量
        alpha, beta       : 成本权重，cost = alpha*|wl_diff| - beta*exp_intensity
    """
    exp_wl = np.array(exp_wl, dtype=float)
    exp_int = np.array(exp_int, dtype=float)
    theo_wl = np.array(theo_wl, dtype=float)
    theo_int = np.array(theo_int, dtype=float)

    # 按实验强度排序，选出前 N 个强峰
    exp_idx_use = np.arange(len(exp_wl))
    if max_high_intensity is not None and len(exp_wl) > max_high_intensity:
        exp_idx_use = np.argsort(-exp_int)[:max_high_intensity]
    
    exp_wl_sel = exp_wl[exp_idx_use]
    exp_int_sel = exp_int[exp_idx_use]
    
    T = len(theo_wl)
    E = len(exp_wl_sel)
    N = max(T, E)
    BIG = 1e6
    
    # 构建成本矩阵
    cost = np.full((N, N), BIG, dtype=float)
    for i in range(T):
        for j in range(E):
            diff = abs(theo_wl[i] - exp_wl_sel[j])
            if diff <= scope:
                cost[i, j] = alpha * diff - beta * exp_int_sel[j]  # 波长差减去强度加权
    
    # 匈牙利算法
    row_ind, col_ind = linear_sum_assignment(cost)
    
    matched_theo = []
    matched_exp = []
    matched_theo_idx = []
    theo_vec = []
    exp_vec = []
    
    for i, j in zip(row_ind, col_ind):
        if i < T and j < E and cost[i,j] < BIG:
            # 匹配成功
            matched_theo.append((theo_wl[i], theo_int[i]))
            matched_exp.append((exp_wl_sel[j], exp_int_sel[j]))
            matched_theo_idx.append(i)
            theo_vec.append(theo_int[i])
            exp_vec.append(exp_int_sel[j])
        else:
            # 未匹配
            theo_vec.append(0)
            exp_vec.append(0)

    return np.array(theo_vec), np.array(exp_vec), matched_theo, matched_exp, np.array(matched_theo_idx, dtype=int)

#施工中的置信度判断策略
def confidence_score(base_elem,element_distance,element_T,element_R2,element_linecounts,final_T,final_R2,final_lc,final_distance,elements_confidence):
    """
    使用说明:base_elem:元素名称列表 element_distance: 元素距离列表 element_T: 元素温度列表 element_R2: 元素R2列表 
    """
    for base_elem, T in element_T.items():
        valid_T = [t for t in T ] #初步验证
        if valid_T:
            TRCD_pairs = []
            R2=element_R2[base_elem]
            LC=element_linecounts[base_elem]
            D=element_distance[base_elem]

            for t,r2,lc,d in zip(T, R2, LC, D):
                TRCD_pairs.append((t, r2, lc,d))

            if TRCD_pairs: 
                filterd_pairs = [pair for pair in TRCD_pairs if pair[0] > 5000 and pair[0] < 20000 ]
                if filterd_pairs:
                    best=max(filterd_pairs, key=lambda x: x[1])
                else:
                    best=(0,0,0,0)
                final_T[base_elem]= best[0]
                final_R2[base_elem]= best[1]
                final_lc[base_elem]= best[2]
                final_distance[base_elem]= best[3] 

    
    for elem, distances in final_distance.items():
        if distances<10000 and final_R2[elem]>0:
            elements_confidence[elem]=np.exp(-1.5*distances/final_R2[elem]) #指数映射
        else:
            elements_confidence[elem]=0

def compute_element_confidence_shape(
    elements,
    peak_wl,
    peak_int,
    global_wl,
    global_intensity,
    scope=0.2,
    plot=False,
    target='KI',
    return_line_payload=False,
    ):
    """
    方案二：用理论和实验谱形的欧几里得距离作为相似度
    elements: 元素数据库 { "ElemI": {"data": [wl, intensity]} }
    peak_wl: 实验寻峰得到的峰位
    peak_int: 实验寻峰得到的峰强度
    scope: 容许匹配窗口 (nm),默认1nm
    """

    match_results = {}
    element_distance = defaultdict(list)
    element_T = defaultdict(list)
    element_R2 = defaultdict(list)
    element_linecounts = defaultdict(list)
    final_results = {} #元素层面显示
    final_T={}
    final_R2={}
    final_lc={}
    final_distance={}
    elements_confidence={}
    Boltzmann_T={}
    Boltzmann_R2={}
    Boltzmann_linecounts={}
    element_line_payload={}
    
    Boltzmann_iterative_T={}
    Boltzmann_iterative_R2={}
    element_iterative_T = defaultdict(list)
    element_iterative_R2 = defaultdict(list)

    #遍历每一个粒子
    for element_name, element_data in elements.items():
        element_matrix = element_data["data"]
        element_wl = element_matrix[:, 0]
        element_intensity = element_matrix[:, 1]
        element_A=element_matrix[:,2]
        element_E=element_matrix[:,3]
        element_g=element_matrix[:,4]

        #reset
        matched_I=[]
        matched_wl=[]
        wl_iterative=[]
        I_iterative=[]
        A_iterative=np.array([], dtype=float)
        E_iterative=np.array([], dtype=float)
        g_iterative=np.array([], dtype=float)


        theo_vec, exp_vec, matched_theo, matched_exp, matched_theo_idx = match_spectral_lines_weighted(
            element_wl,
            element_intensity,
            peak_wl,
            peak_int,
            scope,
        )
        theo_vec = np.array(theo_vec)
        exp_vec = np.array(exp_vec)
        N_total = len(element_wl)
        N_matched = len(matched_exp)
        match_ratio = N_matched / N_total if N_total > 0 else 0 # 匹配率

        matched_theo_idx = np.asarray(matched_theo_idx, dtype=int)
        matched_wl_param = np.asarray(element_wl, dtype=float)[matched_theo_idx].copy() if matched_theo_idx.size > 0 else np.empty((0,), dtype=float)
        matched_intensity_param = np.asarray(element_intensity, dtype=float)[matched_theo_idx].copy() if matched_theo_idx.size > 0 else np.empty((0,), dtype=float)
        matched_A_param = np.asarray(element_A, dtype=float)[matched_theo_idx].copy() if matched_theo_idx.size > 0 else np.empty((0,), dtype=float)
        matched_E_param = np.asarray(element_E, dtype=float)[matched_theo_idx].copy() if matched_theo_idx.size > 0 else np.empty((0,), dtype=float)
        matched_g_param = np.asarray(element_g, dtype=float)[matched_theo_idx].copy() if matched_theo_idx.size > 0 else np.empty((0,), dtype=float)

        # 只传出匹配到的理论谱线参数，便于外部后处理
        element_line_payload[element_name] = {
            'wl': matched_wl_param,
            'intensity': matched_intensity_param,
            'A': matched_A_param,
            'E': matched_E_param,
            'g': matched_g_param,
            'matched_theo_idx': matched_theo_idx.copy(),
            'matched_theo': np.asarray(matched_theo, dtype=float).copy() if len(matched_theo) > 0 else np.empty((0, 2), dtype=float),
            'matched_exp': np.asarray(matched_exp, dtype=float).copy() if len(matched_exp) > 0 else np.empty((0, 2), dtype=float),
        }
        

        
        # 归一化
        if np.sum(theo_vec) > 0:
            theo_vec = theo_vec / np.sum(theo_vec)
        if np.sum(exp_vec) > 0:
            exp_vec = exp_vec / np.sum(exp_vec)

        #此处的ratio改了！
        O_distance =(np.sqrt(np.sum((theo_vec - exp_vec) ** 2)))/(1)  
        if O_distance ==0: #完全没谱线或者只有一条谱线的时候
            O_distance=1e+4

        #BoltzmannT，R2计算
        if len(matched_theo) >= 2:
            # 提取匹配到的谱线参数（与 matched_exp 对应的理论参数）
            matched_wl = np.array([t[0] for t in matched_theo])
            matched_I = np.array([t[1] for t in matched_exp])  # 实验强度

            # 从匹配索引直接取对应的 A、E、g
            slope, intercept, T_fit, R2, y  = Boltzmann_fit(matched_I, matched_wl, matched_A_param, matched_g_param, matched_E_param)
            slope,intecept,T_fit_iterative,R2_itertative,y,E_iterative,wl_iterative,I_iterative,A_iterative,g_iterative=Boltzmann_fit_iterative(matched_I, matched_wl, matched_A_param, matched_g_param, matched_E_param,R2_start_threshold=0.97, max_iter=3, verbose=False)
            
            Boltzmann_T[element_name] = T_fit
            Boltzmann_R2[element_name] = R2
            Boltzmann_linecounts[element_name]= len(matched_theo)
            
            Boltzmann_iterative_T[element_name]=T_fit_iterative
            Boltzmann_iterative_R2[element_name]=R2_itertative

        else:
            Boltzmann_T[element_name] = 0
            Boltzmann_R2[element_name] = 0
            Boltzmann_linecounts[element_name]= 0
            Boltzmann_iterative_T[element_name]=0
            Boltzmann_iterative_R2[element_name]=0
            
        if element_name == target and plot:
            plt.figure(figsize=(7, 5))

           # print(len(E_iterative))
        # 全部理论谱线（浅蓝）
            all_theo_intensity = element_intensity / np.sum(element_intensity)
            for wl, inten_norm in zip(element_wl, all_theo_intensity):
                plt.vlines(wl, 0, inten_norm,
                        color='lightblue', alpha=0.5,
                        label='All Theoretical' if wl==element_wl[0] else "")


            # 理论匹配谱线（蓝）      
            if matched_theo:
                matched_theo_intensity = np.array([inten for _, inten in matched_theo])
                matched_theo_norm = matched_theo_intensity / np.sum(matched_theo_intensity)
                for (wl, _), inten_norm_theo in zip(matched_theo, matched_theo_norm):
                    plt.vlines(wl, 0, inten_norm_theo,
                            color='b', alpha=0.7,
                            label='Matched Theoretical' if wl==matched_theo[0][0] else "")

            # --- 匹配成功的实验谱线（红色） ---
            if matched_exp:
                matched_exp_intensity = np.array([inten for _, inten in matched_exp])
                matched_exp_norm = matched_exp_intensity / np.sum(matched_exp_intensity)
                matched_exp_normalized = [(wl, inten_norm_exp)
                          for (wl, _), inten_norm_exp in zip(matched_exp, matched_exp_norm)]
                
                for (wl, _), inten_norm_exp in zip(matched_exp, matched_exp_norm):
                    plt.vlines(wl, 0, inten_norm_exp,
                            color='r', alpha=0.7,
                            label='Matched Experimental' if wl==matched_exp[0][0] else "")
            for spine in plt.gca().spines.values():
                spine.set_linewidth(1.8)
            for label in plt.gca().get_xticklabels():
                label.set_fontweight("semibold")
            for label in plt.gca().get_yticklabels():
                label.set_fontweight("semibold")

            plt.title(f'Matched Stick Spectrum for {element_name}', fontsize=15, fontweight="semibold")
            plt.xlabel('Wavelength (nm)', fontsize=15, fontweight="semibold")
            plt.ylabel('Normalized Intensity', fontsize=15, fontweight="semibold")
            plt.tick_params(axis='both', which='major', direction='in', top=True, right=True,
                            width=2.0, length=6, labelsize=12)
            plt.tick_params(axis='both', which='minor', direction='in', top=True, right=True,
                            width=2.0, length=6, labelsize=12)
            plt.grid(alpha=0.3)
            plt.legend(loc="upper right", prop={"weight": "semibold", "size": 12}, frameon=False)
            plt.tight_layout()
                    
            ### --- 新增波形标注逻辑 --- ###
            plt.figure(figsize=(7, 5))
            plt.plot(global_wl, global_intensity, color='black', linewidth=2.2, label='Original Spectrum')

            # 标出所有理论谱线位置（浅蓝色线）
            for wl in element_wl:
                plt.axvline(wl, color='cyan', alpha=0.3)

            # 标出匹配到的实验峰（红色点）
            for wl, inten in matched_exp:
                plt.scatter(wl, inten, color='tab:red', s=35)

            for spine in plt.gca().spines.values():
                spine.set_linewidth(1.8)
            for label in plt.gca().get_xticklabels():
                label.set_fontweight("semibold")
            for label in plt.gca().get_yticklabels():
                label.set_fontweight("semibold")

            plt.title(f'Original Spectrum with {element_name} Peaks Marked', fontsize=15, fontweight="semibold")
            plt.xlabel('Wavelength (nm)', fontsize=15, fontweight="semibold")
            plt.ylabel('Intensity', fontsize=15, fontweight="semibold")
            plt.tick_params(axis='both', which='major', direction='in', top=True, right=True,
                            width=2.0, length=6, labelsize=12)
            plt.tick_params(axis='both', which='minor', direction='in', top=True, right=True,
                            width=2.0, length=6, labelsize=12)
            plt.grid(alpha=0.3)
            plt.legend(loc="upper right", prop={"weight": "semibold", "size": 12}, frameon=False)
            plt.tight_layout()

            Boltzmann_plot(matched_exp, matched_theo, element_A, element_E, element_g, element_wl,element_name,mode='normal')
            iterative_combined = np.column_stack((wl_iterative, I_iterative))
            Boltzmann_plot(iterative_combined, iterative_combined, A_iterative, E_iterative, g_iterative, wl_iterative,element_name+"_iterative", mode='iterative')
            plt.show()

        match_results[element_name] = O_distance
        base_elem = ''.join([c for c in element_name if not c.isdigit() and c not in ["I","V"]])
        element_T[base_elem].append(Boltzmann_T[element_name])
        element_R2[base_elem].append(Boltzmann_R2[element_name])
        element_iterative_T[base_elem].append(Boltzmann_iterative_T[element_name])
        element_iterative_R2[base_elem].append(Boltzmann_iterative_R2[element_name])
        element_linecounts[base_elem].append(Boltzmann_linecounts[element_name])
        element_distance[base_elem].append(O_distance)
        

    # print(element_T)


#筛选
#元素距离筛选
    for base_elem, distances in element_distance.items():
        min_distance = min(distances)
        if min_distance < 47.13333:  
            final_results[base_elem] = min_distance
        else:
            final_results[base_elem] = np.mean(distances)
            
#元素T和R2输出
    for base_elem, Ts in element_T.items():
        # 过滤出大于0的温度
        valid_T = [t for t in Ts if t > 0]

        if valid_T:
            # 找出所有符合条件的 (T, R2) 对
            TRC_pairs = []
            if base_elem in element_R2:
                R2s = element_R2[base_elem]
                LCs=element_linecounts[base_elem]
                # 遍历 Ts 列表，筛选出有效温度对应的 R²
                for t, r2 ,lc in zip(Ts, R2s, LCs):
                    # if t > 0 and r2!=1:  # 初筛T>0,R2!=1
                    # if t>0 and lc>2:
                    if t>0 :
                        TRC_pairs.append((t, r2, lc))
            
            if TRC_pairs: 
                # 选出 R² 最大的那一组
                selected_T, selected_R2, selected_LC = max(TRC_pairs, key=lambda x: x[1])
            else:
                # 如果没有 R² 对应信息，就退化为取最小温度
                selected_T = min(valid_T)
                selected_R2 = 0
                selected_LC=0

            # 保存结果
            final_T[base_elem] = selected_T
            final_R2[base_elem] = selected_R2

        else: #如果element_T同时为空
            # if base_elem=='Si': #特殊元素判据
            #     print(f"{base_elem}没有有效温度，无法计算置信度。")
            final_T[base_elem] = 0
            final_R2[base_elem] = 0
          
          
#元素Iterative_T和Iterative_R2输出
    for base_elem, Ts in element_iterative_T.items():
        valid_T = [t for t in Ts if t > 0]

        if valid_T:
            TRC_pairs = []
            if base_elem in element_iterative_R2:
                R2s = element_iterative_R2[base_elem]
                for t, r2 in zip(Ts, R2s):
                    if t > 0:
                        TRC_pairs.append((t, r2))

            if TRC_pairs: 
                selected_T, selected_R2 = max(TRC_pairs, key=lambda x: x[1])
            else:
                selected_T = min(valid_T)
                selected_R2 = 0

            Boltzmann_iterative_T[base_elem] = selected_T
            Boltzmann_iterative_R2[base_elem] = selected_R2

        else:
            Boltzmann_iterative_T[base_elem] = 0
            Boltzmann_iterative_R2[base_elem] = 0


#反归一化置信度输出
    for elem, distances in final_results.items():
        # if elem=='Ca': #特殊元素判据
        #     print(f"{elem}的距离为{distances}，R2为{final_R2[elem]}，T为{final_T[elem]}")
        if distances<10000 and final_R2[elem]>0:
            #elements_confidence[elem]=1/(1+distances) #倒数映射
            elements_confidence[elem]=np.exp(-4.5*distances/final_R2[elem]) #指数映射
            if final_T[elem]<5000 or final_T[elem]>20000: #电子温度判据
                elements_confidence[elem]=0
        else:
            elements_confidence[elem]=0
            # if elem=='Ca': #特殊元素判据
            #    print('1')
    if return_line_payload:
        return match_results,final_results,final_T,final_R2,elements_confidence,element_line_payload
    return match_results,final_results,final_T,final_R2,elements_confidence

 

 #-----数据导入-----

###光谱文件过滤（防止文件夹内奇怪文件的干扰）
def load_spectrum_xy(csv_path):
    """读取光谱前两列并转为数值；若无有效数据则返回 (None, None)。"""
    # 兼容不同来源光谱文件编码（UTF-8/GBK/ANSI 等）
    data = None
    read_errors = []
    for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030", "latin1"):
        try:
            data = pd.read_csv(
                csv_path,
                header=0,
                skipinitialspace=True,
                encoding=enc,
                on_bad_lines='skip',
            )
            break
        except UnicodeDecodeError as e:
            read_errors.append(f"{enc}: {e}")
        except pd.errors.ParserError:
            # 某些文件分隔符/格式异常时回退到 python 引擎自动推断
            try:
                data = pd.read_csv(
                    csv_path,
                    header=0,
                    skipinitialspace=True,
                    encoding=enc,
                    on_bad_lines='skip',
                    sep=None,
                    engine='python',
                )
                break
            except Exception as e:
                read_errors.append(f"{enc}(python-engine): {e}")
        except Exception as e:
            read_errors.append(f"{enc}: {e}")

    if data is None:
        print(f"读取失败，跳过文件: {os.path.basename(csv_path)}")
        return None, None

    if data.shape[1] < 2:
        return None, None

    data = data.iloc[:, :2].copy()
    data.iloc[:, 0] = pd.to_numeric(data.iloc[:, 0], errors='coerce')
    data.iloc[:, 1] = pd.to_numeric(data.iloc[:, 1], errors='coerce')
    data = data.dropna(subset=[data.columns[0], data.columns[1]])

    if data.empty:
        return None, None

    x = data.iloc[:, 0].to_numpy(dtype=float)
    intensity = data.iloc[:, 1].to_numpy(dtype=float)
    return x, intensity


###温度迭代主要程序 
#评价体系
def _candidate_score(confidence, r2):
    # 用置信度和R2偏离惩罚构建评分，减弱局部噪声峰的影响
    return float(confidence) - 0.35 * abs(float(r2) - 1.0)

#top-3算法 算出每轮迭代的候选元素及其对应温度和R2，综合评分选出加权目标温度(target_temperature)
def _pick_target_temperature(candidate_pool, elements_T_main, elements_R2_main, top_k=3):
    ranked = sorted(candidate_pool.items(), key=lambda kv: kv[1], reverse=True)
    top_items = ranked[:max(1, min(top_k, len(ranked)))]

    scores = []
    temperatures = []
    for elem, conf in top_items:
        T_elem = float(elements_T_main.get(elem, 0.0))
        r2_elem = float(elements_R2_main.get(elem, 0.0))
        scores.append(_candidate_score(conf, r2_elem))
        temperatures.append(T_elem)

    scores = np.asarray(scores, dtype=float)
    temperatures = np.asarray(temperatures, dtype=float)
    # softmax加权求目标温度
    shifted = scores - np.max(scores)
    weights = np.exp(shifted)
    weights = weights / max(np.sum(weights), 1e-12)
    return float(np.sum(weights * temperatures)), [e for e, _ in top_items]

##迭代TOP-K+阻尼计算温度算法
#算法内层循环
def T_iteration_single(signal, x, T_initial, max_iterations=10, tolerance=1e-3, candidate_mode='fix',
                       t_min=7000.0, t_max=20000.0, alpha=0.35, top_k=3):
    T = float(np.clip(T_initial, t_min, t_max))
    top_candidate_element = None
    top_candidate_element_T = 0.0
    top_candidate_confidence = 0.0
    top_candidate_R2 = 0.0
    fixed_element = None
    best_score = -np.inf
    stable_rounds = 0

    if candidate_mode not in ('fix', 'alterable'):
        raise ValueError("candidate_mode 只能是 'fix' 或 'alterable'")

    for iteration in range(max_iterations):
        elements_main, elements_main_list = elements_database_pt2(folder_path, T)
        true_peak_idx, peak_wl, peak_int = wavelet_peak_detection(
            signal,
            x,
            wavelet='mexh',
            scales=np.arange(1, 11),
            neighbor=4,
            min_length=3,
            coeffi_threshold=700,
            window=5,
        )
        particle_main, elements_main, elements_T_main, elements_R2_main, elements_confidence_main = compute_element_confidence_shape(
            elements_main,
            peak_wl,
            peak_int,
            x,
            signal,
            scope=0.3,
        )

        if not elements_confidence_main:
            print("没有最概然元素")
            break

        valid_candidates = {
            elem: conf
            for elem, conf in elements_confidence_main.items()
            if float(elements_R2_main.get(elem, 0.0)) != 1.0
        }
        candidate_pool = valid_candidates if valid_candidates else elements_confidence_main

        #获得目标温度
        target_temperature, ranked_elements = _pick_target_temperature(
            candidate_pool,
            elements_T_main,
            elements_R2_main,
            top_k=top_k,
        )

        if candidate_mode == 'fix':
            # 首轮锁定最概然元素，后续迭代不再改变元素身份
            if fixed_element is None:
                fixed_element = max(candidate_pool, key=candidate_pool.get)
                # print(
                #     f"第 {iteration + 1} 轮迭代，锁定最概然元素: {fixed_element}，"
                #     f"此时温度为：{float(elements_T_main.get(fixed_element, 0.0))}"
                # )

            if fixed_element not in elements_T_main:
                # print(f"固定元素 {fixed_element} 在当前迭代结果中不存在，停止迭代")
                break

            top_candidate_element = fixed_element

        else:
            # 每轮允许最概然元素变化
            top_candidate_element = max(candidate_pool, key=candidate_pool.get)

        top_candidate_element_T = float(elements_T_main.get(top_candidate_element, 0.0))
        top_candidate_confidence = float(elements_confidence_main.get(top_candidate_element, 0.0))
        top_candidate_R2 = float(elements_R2_main.get(top_candidate_element, 0.0))
        # print(
        #     f"最概然元素: {top_candidate_element}，对应温度: {top_candidate_element_T:.4f} K，"
        #     f"置信度: {top_candidate_confidence:.4f}，R2: {top_candidate_R2:.4f}"
        # )

        current_score = _candidate_score(top_candidate_confidence, top_candidate_R2)
        if current_score > best_score:
            best_score = current_score

        # 阻尼更新目标温度
        previous_T = T
        T = (1.0 - alpha) * T + alpha * target_temperature
        T = float(np.clip(T, t_min, t_max))

        # 双条件收敛：温度变化足够小，且连续两轮稳定
        denom = max(abs(T), 1e-12)
        rel_change = abs(T - previous_T) / denom
        if rel_change < tolerance:
            stable_rounds += 1
        else:
            stable_rounds = 0

        if stable_rounds >= 2:
            # print(f"迭代收敛于 T={T:.4f} K，迭代次数={iteration + 1}")
            break

        # print(
        #     f"候选集(top-{min(top_k, len(ranked_elements))}): {ranked_elements}，"
        #     f"加权目标温度: {target_temperature:.4f} K，更新后温度: {T:.4f} K"
        # )

    return T, top_candidate_element, top_candidate_element_T, top_candidate_confidence, best_score
#算法外层循环（全局搜索）
def T_iteration(signal, x, T_initial, max_iterations=10, tolerance=1e-3, candidate_mode='fix',
                t_min=7000.0, t_max=25000.0, multistart_count=9, alpha=0.35, top_k=3):
    
    # 支持单初值和多初值；默认会在温度区间内自动多起点
    if isinstance(T_initial, (list, tuple, np.ndarray)):
        initial_points = [float(t) for t in T_initial]
    else:
        if multistart_count <= 1:
            initial_points = [float(T_initial)]
        else:
            initial_points = np.linspace(float(t_min), float(t_max), int(multistart_count)).tolist()

    best_result = None
    best_score = -np.inf

    for idx, t0 in enumerate(initial_points):
        # print(color_text(f"\n[多起点] 第 {idx + 1}/{len(initial_points)} 个初值: T0={float(t0):.2f} K", BLUE))
        result = T_iteration_single(
            signal,
            x,
            t0,
            max_iterations=max_iterations,
            tolerance=tolerance,
            candidate_mode=candidate_mode,
            t_min=t_min,
            t_max=t_max,
            alpha=alpha,
            top_k=top_k,
        )
        current_score = float(result[4])
        if current_score > best_score:
            best_score = current_score
            best_result = result

    if best_result is None:
        return float(T_initial), None, 0.0, 0.0

    # print(color_text(f"[多起点] 选择全局最优结果，评分={best_score:.4f}", GREEN))
    return best_result[0], best_result[1], best_result[2], best_result[3]

#遍历暴力求解算法

def Brute_Force_T_iteration(signal, x, t_min=7000.0, t_max=25000.0, t_step=250.0):
    if t_step <= 0:
        raise ValueError("t_step 必须大于 0")
    if t_max < t_min:
        raise ValueError("t_max 必须大于等于 t_min")

    # 峰位仅依赖原始光谱，与温度无关，放到循环外减少重复计算
    true_peak_idx, peak_wl, peak_int = wavelet_peak_detection(
        signal,
        x,
        wavelet='mexh',
        scales=np.arange(1, 11),
        neighbor=4,
        min_length=3,
        coeffi_threshold=700,
        window=5,
    )

    temperature_grid = np.arange(float(t_min), float(t_max) + 0.5 * float(t_step), float(t_step))

    best_scan_T = None
    best_element = None
    best_element_T = 0.0
    best_confidence = -np.inf
    best_R2 = 0.0

    for scan_idx, scan_T in enumerate(temperature_grid, start=1):
        elements_main, elements_main_list = elements_database_pt2(folder_path, float(scan_T))
        particle_main, elements_main, elements_T_main, elements_R2_main, elements_confidence_main = compute_element_confidence_shape(
            elements_main,
            peak_wl,
            peak_int,
            x,
            signal,
            scope=0.3,
        )

        if not elements_confidence_main:
            continue

        candidate_element = max(elements_confidence_main, key=elements_confidence_main.get)
        candidate_confidence = float(elements_confidence_main.get(candidate_element, 0.0))
        candidate_element_T = float(elements_T_main.get(candidate_element, 0.0))
        candidate_R2 = float(elements_R2_main.get(candidate_element, 0.0))

        print(
            f"[穷举 {scan_idx}/{len(temperature_grid)}] 扫描温度={float(scan_T):.2f} K，"
            f"最概然元素={candidate_element}，置信度={candidate_confidence:.4f}，R2={candidate_R2:.4f}"
        )

        if candidate_confidence > best_confidence:
            best_confidence = candidate_confidence
            best_scan_T = float(scan_T)
            best_element = candidate_element
            best_element_T = candidate_element_T
            best_R2 = candidate_R2

    if best_element is None:
        print("穷举结束：未找到有效候选元素")
        return float(t_min), None, 0.0, 0.0

    print(
        color_text(
            f"[穷举最优] 扫描温度={best_scan_T:.2f} K，最概然元素={best_element}，"
            f"元素温度={best_element_T:.4f} K，置信度={best_confidence:.4f}，R2={best_R2:.4f}",
            GREEN,
        )
    )
    return best_scan_T, best_element, best_element_T, best_confidence

#温度扫描——元素勘误
def scan_target_element_confidence(peak_wl,peak_int,x,intensity_sum,target_elem,elements_confidence_main,t_min=5000.0,t_max=20000.0,t_step=250.0,):

    """扫描温度区间并返回指定元素置信度曲线。"""
    if t_step <= 0:
        raise ValueError("t_step 必须大于 0")
    if t_max < t_min:
        raise ValueError("t_max 必须大于等于 t_min")

    temperature_grid = np.arange(float(t_min), float(t_max) + 0.5 * float(t_step), float(t_step))
    target_confidences = []

    for scan_idx, scan_T in enumerate(temperature_grid, start=1):

        elements_rockmain = [elem for elem, conf in elements_confidence_main.items() if conf > 0.7]
        elements_rareearth, _ = elements_database_lineswitch(folder_path2, float(scan_T), elements_rockmain, LineSwitchMode=True)
        _, _, _, _, elements_confidence = compute_element_confidence_shape(
            elements_rareearth,
            peak_wl,
            peak_int,
            x,
            intensity_sum,
            scope=0.2,
            plot=False,
        )

        conf_value = float(elements_confidence.get(target_elem, 0.0))
        target_confidences.append(conf_value)


    return temperature_grid, np.asarray(target_confidences, dtype=float)

#谱线波段节选
def extract_spectrum_between_minima(x, y, wl_a, ratio=1):
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    valid_mask = np.isfinite(x_arr) & np.isfinite(y_arr)
    x_arr = x_arr[valid_mask]
    y_arr = y_arr[valid_mask]

    if x_arr.size < 3:
        return x_arr, y_arr, None, None

    order = np.argsort(x_arr)
    x_arr = x_arr[order]
    y_arr = y_arr[order]

    center_wl = float(wl_a)

    local_minima = np.where((y_arr[1:-1] <= y_arr[:-2]) & (y_arr[1:-1] <= y_arr[2:]))[0] + 1
    if local_minima.size == 0:
        return x_arr, y_arr, x_arr[0], x_arr[-1]

    left_candidates = local_minima[x_arr[local_minima] < center_wl]
    right_candidates = local_minima[x_arr[local_minima] > center_wl]

    peak_left_idx = left_candidates[-1] if left_candidates.size > 0 else 0
    peak_right_idx = right_candidates[0] if right_candidates.size > 0 else x_arr.size - 1
    peak_region = np.arange(peak_left_idx, peak_right_idx + 1)
    peak_idx = int(peak_region[np.argmax(y_arr[peak_region])])
    peak_y = float(y_arr[peak_idx])
    print(f"中心波长: {center_wl}, 峰顶波长: {x_arr[peak_idx]}, 峰值强度: {peak_y}")
    valley_limit = peak_y * float(ratio)

    left_idx = 0
    for idx in left_candidates[::-1]:
        if y_arr[idx] <= valley_limit:
            left_idx = idx
            break

    right_idx = x_arr.size - 1
    for idx in right_candidates:
        if y_arr[idx] <= valley_limit:
            right_idx = idx
            break

    if left_idx > right_idx:
        left_idx, right_idx = right_idx, left_idx

    return x_arr[left_idx:right_idx + 1], y_arr[left_idx:right_idx + 1], x_arr[left_idx], x_arr[right_idx]

###选线拟合策略

#元素名称
def base_element_name(element_name):
    return ''.join([c for c in str(element_name) if not c.isdigit() and c not in ["I", "V"]])

#选取置信度为0的元素
def filter_elements_by_base(elements, target_base_elements):
    target_base_set = {str(elem).strip().upper() for elem in target_base_elements}
    return {
        element_name: element_data
        for element_name, element_data in elements.items()
        if base_element_name(element_name).upper() in target_base_set
    }

#拟合峰加入
def build_coarse_matched_fit_lines(element_line_payload, target_base_elements):
    columns = ["Element", "BaseElement", "PeakIndex", "TargetWavelength", "SourceElement"]
    target_base_set = {str(elem).strip().upper() for elem in target_base_elements}
    rows = []

    for element_name, payload in element_line_payload.items():
        base_elem = base_element_name(element_name)
        if base_elem.upper() not in target_base_set:
            continue

        matched_theo = np.asarray(payload.get("matched_theo", []), dtype=float)
        if matched_theo.size == 0:
            matched_wl = np.asarray(payload.get("wl", []), dtype=float)
        else:
            matched_theo = np.atleast_2d(matched_theo)
            matched_wl = matched_theo[:, 0]

        matched_idx = np.asarray(payload.get("matched_theo_idx", []), dtype=int)
        for pos, wl_value in enumerate(matched_wl):
            if not np.isfinite(wl_value):
                continue
            peak_index = int(matched_idx[pos]) if pos < matched_idx.size else int(pos)
            rows.append({
                "Element": element_name,
                "BaseElement": base_elem,
                "PeakIndex": peak_index,
                "TargetWavelength": float(wl_value),
                "SourceElement": "COARSE_MATCHED",
            })

    if not rows:
        return pd.DataFrame(columns=columns)

    return (
        pd.DataFrame(rows, columns=columns)
        .drop_duplicates(["Element", "TargetWavelength"])
        .reset_index(drop=True)
    )


def append_fitted_peak_candidates(peak_wl, peak_int, target_fit_params):
    peak_wl_arr = pd.to_numeric(pd.Series(peak_wl), errors="coerce").to_numpy(dtype=float)
    peak_int_arr = pd.to_numeric(pd.Series(peak_int), errors="coerce").to_numpy(dtype=float)
    valid_peak_mask = np.isfinite(peak_wl_arr) & np.isfinite(peak_int_arr)

    if target_fit_params is None or target_fit_params.empty:
        return peak_wl_arr[valid_peak_mask], peak_int_arr[valid_peak_mask]

    fit_wl = pd.to_numeric(target_fit_params["TargetWavelength"], errors="coerce").to_numpy(dtype=float)
    fit_int = pd.to_numeric(target_fit_params["A"], errors="coerce").to_numpy(dtype=float)
    valid_fit_mask = np.isfinite(fit_wl) & np.isfinite(fit_int) & (fit_int > 0)

    return (
        np.concatenate([peak_wl_arr[valid_peak_mask], fit_wl[valid_fit_mask]]),
        np.concatenate([peak_int_arr[valid_peak_mask], fit_int[valid_fit_mask]]),
    )


def MultiPeakFit(
    folder_path,
    elements_rockmain,
    spectrum_payload,
    target_base_elements=None,
    target_fit_lines=None,
    plot_fit_windows=False,
):
    target_fit_columns = [
        "Element",
        "BaseElement",
        "SourceElement",
        "PeakIndex",
        "TargetWavelength",
        "A",
        "mu",
        "sigma",
        "MuAbsDiff",
        "FitComponentCount",
        "FitLineSource",
    ]
    target_fit_rows = []
    target_base_set = None
    if target_base_elements is not None:
        target_base_set = {str(elem).strip().upper() for elem in target_base_elements}
        if len(target_base_set) == 0:
            return pd.DataFrame(target_fit_rows, columns=target_fit_columns)

    if target_fit_lines is None:
        target_fit_lines = pd.DataFrame(columns=["Element", "PeakIndex", "TargetWavelength", "SourceElement"])
    else:
        target_fit_lines = target_fit_lines.copy()
        if "TargetWavelength" in target_fit_lines.columns:
            target_fit_lines["TargetWavelength"] = pd.to_numeric(
                target_fit_lines["TargetWavelength"],
                errors="coerce",
            )

    file_list = glob.glob(os.path.join(folder_path, "*.csv"))
    elements_list = [os.path.splitext(os.path.basename(f))[0] for f in file_list]
    elements = {}
    for element_name in elements_list: 
        target_base_elem = base_element_name(element_name)
        if target_base_set is not None and target_base_elem.upper() not in target_base_set:
            continue
        if True:
            file_path = os.path.join(folder_path, element_name + ".csv")
            df = pd.read_csv(file_path, header=0, encoding="gbk")
            coarse_target_rows_for_file = target_fit_lines.loc[
                target_fit_lines.get("Element", pd.Series(dtype=object)).astype(str) == element_name
            ].copy()
            if df.shape[1] <= 9 and not coarse_target_rows_for_file.empty:
                df = df.copy()
                df["conflict_elem"] = np.nan
            if df.shape[1] > 9:
                df = df.iloc[1::2].copy()
                wl = df.iloc[:, 1]*0.1
                pure_element_flag = df.iloc[:, 9]
                normalized_pure_element = pure_element_flag.astype(str).str.strip().str.upper()
                rock_line_columns = ["Element", "Wavelength", "LineIntensity", "LineType"]
                rock_line_rows = []
                rock_line_dir = r"D:\LIBS\RREdetectation\RockBaseElemLines\Linespectrum"

                for elem_toremove in elements_rockmain:
                    elem_toremovelines = pd.read_csv(
                        os.path.join(rock_line_dir, elem_toremove + ".csv"),
                        header=0,
                        encoding="gbk",
                    )

                    # 数据清洗
                    line_wl_col = elem_toremovelines.columns[0]
                    line_intensity_cols = list(elem_toremovelines.columns[1:4])
                    elem_toremovelines[line_wl_col] = pd.to_numeric(elem_toremovelines[line_wl_col], errors='coerce')
                    elem_toremovelines[line_intensity_cols] = elem_toremovelines[line_intensity_cols].replace(r'^\s*$', np.nan, regex=True)
                    elem_toremovelines[line_intensity_cols] = elem_toremovelines[line_intensity_cols].apply(pd.to_numeric, errors='coerce')
                    intensity_valid_mask = elem_toremovelines[line_intensity_cols].notna()
                    elem_toremovelines["LineIntensity"] = elem_toremovelines[line_intensity_cols].bfill(axis=1).iloc[:, 0]
                    # linetype标记
                    elem_toremovelines["LineType"] = np.where(
                        intensity_valid_mask.any(axis=1),
                        intensity_valid_mask.idxmax(axis=1),
                        np.nan,
                    )

                    line_wl_np = elem_toremovelines[line_wl_col].to_numpy(dtype=float)
                    line_intensity_np = elem_toremovelines["LineIntensity"].to_numpy(dtype=float)
                    line_type_np = elem_toremovelines["LineType"].to_numpy(dtype=object)
                    valid_line_mask = np.isfinite(line_wl_np)
                    if np.any(valid_line_mask):
                        rock_line_rows.append(np.column_stack([
                            np.full(np.count_nonzero(valid_line_mask), elem_toremove, dtype=object),
                            line_wl_np[valid_line_mask],
                            line_intensity_np[valid_line_mask],
                            line_type_np[valid_line_mask],
                        ]))

                elements_rockmain_lines_np = (
                    np.vstack(rock_line_rows)
                    if rock_line_rows
                    else np.empty((0, len(rock_line_columns)), dtype=object)
                )
                #处理后element_rockmain_lines_np存在元素、波长、强度、类型四列，后续根据元素和波长筛选谱线进行拟合选线

                #后续处理（elements_rockmain_lines_np ）
                line_wl_col = "Wavelength"
                all_elem_toremovelines = pd.DataFrame(elements_rockmain_lines_np, columns=rock_line_columns)
                all_elem_toremovelines[line_wl_col] = pd.to_numeric(
                    all_elem_toremovelines[line_wl_col],
                    errors='coerce',
                )
                all_elem_toremovelines["LineIntensity"] = pd.to_numeric(
                    all_elem_toremovelines["LineIntensity"],
                    errors='coerce',
                )

                coarse_target_rows = target_fit_lines.loc[
                    target_fit_lines.get("Element", pd.Series(dtype=object)).astype(str) == element_name
                ].copy()
                fit_source_lookup = {}
                fit_peak_index_lookup = {}

                if not coarse_target_rows.empty:
                    wl_tofit = pd.Series(
                        pd.to_numeric(coarse_target_rows["TargetWavelength"], errors="coerce").to_numpy(dtype=float),
                        index=coarse_target_rows.index,
                    ).dropna()
                    fit_source_lookup = coarse_target_rows.get(
                        "SourceElement",
                        pd.Series("COARSE_MATCHED", index=coarse_target_rows.index),
                    ).astype(str).to_dict()
                    fit_peak_index_lookup = pd.to_numeric(
                        coarse_target_rows.get("PeakIndex", pd.Series(-1, index=coarse_target_rows.index)),
                        errors="coerce",
                    ).fillna(-1).astype(int).to_dict()
                    fit_line_source = "coarse_matched"
                    print(color_text(
                        f"{element_name} 使用粗检测已匹配谱线进行多峰拟合，不再按 normalized_pure_element 筛选",
                        GREEN,
                    ))
                else:
                    fit_peak_indices = normalized_pure_element[
                        normalized_pure_element.isin(elements_rockmain)
                    ].index
                    wl_tofit = pd.to_numeric(wl.loc[fit_peak_indices], errors='coerce').dropna() #匹配后存在的基体元素的全部谱线
                    fit_line_source = "normalized_pure_element"

                if coarse_target_rows.empty:
                    fit_line_source = "normalized_pure_element"

                if wl_tofit.empty:
                    print(color_text(f"{element_name} No conflict elements", YELLOW))

                wl_tofit_count = len(wl_tofit)
                if wl_tofit_count > 0:
                    print(color_text(
                        f"{element_name} 需要多峰拟合处理的谱线数量: {wl_tofit_count}",
                        BLUE,
                    ))

                for fit_count, (peak_index, wl_value) in enumerate(wl_tofit.items(), start=1):
                    if fit_line_source == "coarse_matched":
                        source_elem = fit_source_lookup.get(peak_index, "COARSE_MATCHED")
                        output_peak_index = int(fit_peak_index_lookup.get(peak_index, -1))
                    else:
                        source_elem = normalized_pure_element.loc[peak_index]
                        output_peak_index = int(peak_index)
                    print(color_text(
                        (
                            f"[{fit_count}/{wl_tofit_count}] 正在处理多峰拟合谱线: "
                            f"目标元素={element_name}, "
                            f"重叠基体元素={source_elem}, "
                            f"PeakIndex={output_peak_index}, "
                            f"Wavelength={float(wl_value):.4f} nm"
                        ),
                        BLUE,
                    ))
                    #回到原始光谱寻找峰值极小值
                    segment_wl, segment_signal, left_min_wl, right_min_wl = extract_spectrum_between_minima(
                        x,
                        signal,
                        wl_value,
                    )
                    lines_in_window = pd.DataFrame(columns=rock_line_columns)

                    if segment_wl.size == 0:
                        print(color_text(
                            f"拟合波长 {wl_value:.4f} 未截取到有效原始光谱窗口，跳过该峰位",
                            YELLOW,
                        ))
                        continue
                                
                    if segment_wl.size > 0:
                        print(
                            f"原始光谱截取窗口: {left_min_wl:.4f} - {right_min_wl:.4f}, 点数: {segment_wl.size},拟合波长 {wl_value:.4f}",

                        )
                        line_left = min(float(left_min_wl), float(right_min_wl))
                        line_right = max(float(left_min_wl), float(right_min_wl))
                                    
                        #窗口选线：从所有 elements_rockmain 的谱线里一起筛选
                        lines_in_window = all_elem_toremovelines.loc[
                            all_elem_toremovelines[line_wl_col].between(line_left, line_right, inclusive="both")
                            & all_elem_toremovelines["LineIntensity"].notna(),
                            ["Element", line_wl_col, "LineIntensity", "LineType"],
                        ].copy()
                        if lines_in_window.empty:
                            print(color_text(
                                f"所有基体元素在 {line_left:.4f} - {line_right:.4f} nm 范围内没有谱线",
                                YELLOW,
                            ))
                        else:
                            lines_in_window = lines_in_window.sort_values(["Element", line_wl_col]).reset_index(drop=True)
                            # print(color_text(
                            #     f"所有基体元素在 {line_left:.4f} - {line_right:.4f} nm 范围内的全部谱线:",
                            #     GREEN,
                            # ))
                            # print(lines_in_window.to_string(index=False))
                                
                                
                    #拟合选线逻辑
                    strongest_lines = []
                    fit_boundary_line_wl = None
                    if segment_wl.size > 0 and not lines_in_window.empty:
                        strongest_line_rows = lines_in_window.nlargest(2, "LineIntensity")
                        strongest_lines = strongest_line_rows[line_wl_col].astype(float).tolist()
                        fit_boundary_line_wl = float(strongest_line_rows.iloc[0][line_wl_col])
                        strongest_line_summary = ", ".join(
                            f"{row['Element']} {float(row[line_wl_col]):.4f} nm, intensity={float(row['LineIntensity']):.4e}"
                            for _, row in strongest_line_rows.iterrows()
                        )
                        print(color_text(
                            f"选中用于拟合的所有基体元素最强前 {len(strongest_lines)} 条谱线: {strongest_line_summary}",
                            GREEN,
                        ))

                    #拟合数值显示
                    if plot_fit_windows and segment_wl.size > 0:
                        plt.figure(figsize=(7, 5))
                        plt.plot(
                            segment_wl,
                            segment_signal,
                            color='tab:blue',
                            linewidth=2.2,
                            label='Extracted spectrum',
                        )
                        plt.axvline(
                            wl_value,
                            color='tab:green',
                            linewidth=2.0,
                            linestyle='--',
                            label=f'{element_name}: {wl_value:.4f}',
                        )
                                    
                        for line_element, line_wavelength, line_intensity, line_type in lines_in_window[
                            ["Element", line_wl_col, "LineIntensity", "LineType"]
                        ].itertuples(index=False, name=None):
                            line_wavelength = float(line_wavelength)
                            is_selected_line = any(
                                np.isclose(line_wavelength, selected_line)
                                for selected_line in strongest_lines
                            )
                            plt.axvline(
                                line_wavelength,
                                color='tab:orange' if is_selected_line else 'tab:red',
                                linewidth=2.0,
                                linestyle='--',
                            )


                        ax = plt.gca()
                        for spine in ax.spines.values():
                            spine.set_linewidth(1.8)
                        for label in ax.get_xticklabels():
                            label.set_fontweight("semibold")
                        for label in ax.get_yticklabels():
                            label.set_fontweight("semibold")

                        plt.xlabel('Wavelength', fontsize=15, fontweight="semibold")
                        plt.ylabel('Intensity', fontsize=15, fontweight="semibold")
                        plt.title(
                            f'{element_name} vs All Rock Main Elements Spectrum Window',
                            fontsize=15,
                            fontweight="semibold",
                        )

                        plt.tick_params(axis='both', which='major', direction='in', top=True, right=True, width=2.0, length=6, labelsize=12)
                        plt.tick_params(axis='both', which='minor', direction='in', top=True, right=True, width=2.0, length=6, labelsize=12)
                        plt.grid(alpha=0.3)
                        plt.legend(loc="upper right", prop={"weight": "semibold", "size": 12}, frameon=False)
                        plt.tight_layout()
                        #plt.show()
                                
                    segment_wl = pd.Series(pd.to_numeric(segment_wl, errors='coerce'))
                    segment_signal = pd.Series(pd.to_numeric(segment_signal, errors='coerce'))

                    valid_mask=segment_wl.notna() & segment_signal.notna()
                    segment_wl=segment_wl[valid_mask].reset_index(drop=True)
                    segment_signal=segment_signal[valid_mask].reset_index(drop=True)
                                
                    #基线部分
                    # segment_signal = segment_signal - segment_signal.min()
                                
                                
                    # 自动找局部极大值
                    extrema_idx = []
                    for i in range(1, len(segment_signal) - 1):
                        is_local_max = segment_signal.iloc[i] > segment_signal.iloc[i - 1] and segment_signal.iloc[i] > segment_signal.iloc[i + 1]
                        if is_local_max:
                            extrema_idx.append(i)

                    manual_peak_wl = [float(wl_value)]
                    manual_peak_wl.extend(float(line_wavelength) for line_wavelength in strongest_lines)
                    print(color_text(f"手动峰位列表: {manual_peak_wl}", BLUE))
                                
                    if len(manual_peak_wl) > 0:
                        wl_np_for_peak = segment_wl.to_numpy(dtype=float)
                        int_np_for_peak = segment_signal.to_numpy(dtype=float)
                        sort_idx_for_peak = np.argsort(wl_np_for_peak)
                        wl_sorted_for_peak = wl_np_for_peak[sort_idx_for_peak]
                        int_sorted_for_peak = int_np_for_peak[sort_idx_for_peak]

                        manual_peak_wl_np = np.asarray(manual_peak_wl, dtype=float)
                        in_range_mask = (
                            (manual_peak_wl_np >= wl_sorted_for_peak[0])
                            & (manual_peak_wl_np <= wl_sorted_for_peak[-1])
                        )
                        if not np.all(in_range_mask):
                            skipped_peak_wl = manual_peak_wl_np[~in_range_mask]
                            print(color_text(f"跳过超出截取窗口、无法插值的手动峰位: {skipped_peak_wl.tolist()}", YELLOW))

                        manual_peak_wl_np = np.sort(manual_peak_wl_np[in_range_mask])
                        peak_wl = pd.Series(manual_peak_wl_np)
                        peak_int = pd.Series(np.interp(manual_peak_wl_np, wl_sorted_for_peak, int_sorted_for_peak))

                        # FWHM 估计仍基于离散 CWT 结果，这里只保留最近采样点索引用于估计峰宽。
                        extrema_idx = sorted(int(np.argmin(np.abs(wl_np_for_peak - target_mu))) for target_mu in manual_peak_wl_np)

                    if len(extrema_idx) == 0:
                        raise ValueError('未找到可用峰位，请检查数据或 manual_peak_wl 设置。')

                    if len(manual_peak_wl) == 0:
                        peak_wl = segment_wl.iloc[extrema_idx]
                        peak_int = segment_signal.iloc[extrema_idx]


                    #类调用
                    estimator=CWTPeakFWHMEstimator(segment_wl, segment_signal,scale=0.48,threshold=0.01)
                    cwt_peaks, cwt_fwhm, cwt_data=estimator.cwt_peak_detection()
                                
                    wl_np = np.asarray(segment_wl, dtype=float)
                    peak_indices = np.asarray(extrema_idx, dtype=int)
                    peak_indices = peak_indices[(peak_indices >= 0) & (peak_indices < len(wl_np))]

                    selected_idx = np.sort(peak_indices)
                    fwhm_selected = estimator.estimate_fwhm(np.asarray(cwt_data, dtype=float), selected_idx, wl_np)
                    print(color_text(f"Fitted FWHM: {fwhm_selected}", RED))
                                
                    fit_left_mu = None
                    fit_right_mu = None
                    # if fit_boundary_line_wl is not None and np.isfinite(fit_boundary_line_wl):
                    #     fit_left_mu, fit_right_mu = sorted([float(wl_value), fit_boundary_line_wl])
                                
                    fitter = GaussMultiPeakFitter(
                        wl=segment_wl.to_numpy(dtype=float),
                        rel_int=segment_signal.to_numpy(dtype=float),
                        extrema_idx=extrema_idx,
                        fwhm_selected=fwhm_selected,
                        wl_np=wl_np,
                        selected_idx=selected_idx,
                        peak_mu=peak_wl.to_numpy(dtype=float),
                        peak_height_upper=peak_int.to_numpy(dtype=float),
                        fit_left_mu=fit_left_mu,
                        fit_right_mu=fit_right_mu,
                    )
                    fitter.fit()

                    #fitter.plot(peak_wl=peak_wl.to_numpy(dtype=float), peak_int=peak_int.to_numpy(dtype=float))

                    #拟合数据传回处理
                    fitted_params_arr = np.asarray(fitter.fitted_params, dtype=float)
                    
                    if fitted_params_arr.size == 0:
                        print(color_text(
                            f"拟合波长 {float(wl_value):.4f} 未得到 fitted_params",
                            YELLOW,
                        ))
                        continue

                    
                    mu_diff = np.abs(fitted_params_arr[:, 1] - float(wl_value))
                    target_fit_idx = int(np.argmin(mu_diff))
                    target_A, target_mu, target_sigma = fitted_params_arr[target_fit_idx]

                    target_fit_rows.append({
                        "Element": element_name,
                        "BaseElement": target_base_elem,
                        "SourceElement": source_elem,
                        "PeakIndex": output_peak_index,
                        "TargetWavelength": float(wl_value),
                        "A": float(target_A),
                        "mu": float(target_mu),
                        "sigma": float(target_sigma),
                        "MuAbsDiff": float(mu_diff[target_fit_idx]),
                        "FitComponentCount": int(fitted_params_arr.shape[0]),
                        "FitLineSource": fit_line_source,
                    })

                    print(color_text(
                        (
                            f"目标峰 fitted_params: "
                            f"wl_tofit={float(wl_value):.4f}, "
                            f"A={float(target_A):.6g}, "
                            f"mu={float(target_mu):.6f}, "
                            f"sigma={float(target_sigma):.6g}"
                        ),
                        GREEN,
                    ))
                    print()
                    



    return pd.DataFrame(target_fit_rows, columns=target_fit_columns)


###数据库导入
folder_path = r'D:\LIBS\RREdetectation\Elements_database' #元素库路径
folder_path2 =r'D:\LIBS\RREdetectation\Rareearth_pt3' #稀土元素光谱路径 Lineswitch Mode（threshold=0.15nm）(pt2:0.2nm)


#attention:elements_database_pt2 header=1 
signal_path1= r'D:\LIBS\RREdetectation\SpecSimuDatabase' #普通元素光谱数据库   a.t%
signal_path2= r'D:\LIBS\RREdetectation\Rareearth\Spectrum' #稀土元素光谱100%   a.t%
signal_path3= r'D:\LIBS\RREdetectation\RREs' #岩石基体95%+稀土元素光谱5%   a.t%
signal_path4= r'D:\LIBS\RREdetectation\RREs\last3' #Sm、Tb、Gd最后三种的高接纳度测试
signal_path5= r'D:\LIBS\RREdetectation\Rockbasespectral' #八大岩石基体元素检测
signal_path6= r'D:\LIBS\RREdetectation\Rockbasespectral_15' #八大岩石基体元素检测最后三种的高接纳度测试
signal_path7= r'D:\LIBS\RREdetectation\Rockbasespectral_11_10e16' #普通元素光谱数据库最后三种的高接纳度测试
signal_path8= r'D:\LIBS\RREdetectation\Rockbasespectral_11_0.75eV' #低电子温度（低多普勒展宽）测试
signal_path9= r'D:\LIBS\RREdetectation\Rockbasespectral_11_0.5eV' #高电子温度（高多普勒展宽）测试

signal_path10= r'D:\LIBS\RREdetectation\RandomSpectrum_av2\Pt1' #随机光谱测试
RandPerfOPbotton=False #随机光谱性能测试模式

###每次运行前均需调整下列参数！！！
T_initial=10000
target_path=signal_path10 #光谱路径·
I_file_list = glob.glob(os.path.join(target_path, "*.csv"))
I_elements_list = [os.path.splitext(os.path.basename(f))[0] for f in I_file_list]
# print(I_elements_list)
target_files=['070101_95_random'] #待测光谱文件名列表（不带扩展名）
target_element='Pr' #指定元素（仅在 specifybotton=True 时生效）
plottarget='TbII'#指定绘图元素（仅在 plotbotton=True 时生效）

TargetTempScanMode=False #指定元素温度扫描模式（5000-20000 K）
scan_target_element='Yb' #温度扫描模式下的目标元素
scan_t_min=3000
scan_t_max=25000
scan_t_step=100

AutoElemTempMarkMode=False #自动扫描有置信度稀土元素并在输出中标注温度敏感性
auto_mark_conf_min=0.05 #参与扫描的最小置信度阈值
auto_mark_delta_threshold=0.5 #最大-最小置信度差值超过该阈值则标注

specifybotton = False  # True: 遍历全部文件，仅输出目标元素；False: 只跑 target_files，输出全部元素 （全文件，单元素）
checkallbutton=False#是否检测文件内的全部光谱 （全文件）
plotbotton=False#展示Boltzmann图
save2csvbotton=False #是否保存稀土元素置信度结果到CSV
printbotton=True #是否打印元素检测结果
Titerationbotton=False #是否启用温度迭代算法
ReturnRawLinePayloadMode=False #是否返回每个元素的原始谱线参数( wl/intensity/A/E/g/matched_* )



# 模式控制逻辑：绘图模式优先级最高，开启后强制关闭其他模式；指定元素模式优先级次之，开启后覆盖文件筛选但不影响绘图设置
# 绘图模式开启时强制关闭 specify、checkall，仅输出目标图像但全量跑文件
if plotbotton:
    specifybotton = False
    checkallbutton = False
    save2csvbotton = False

# 指定元素温度扫描模式：强制关闭温度迭代，按温度区间扫描并绘制置信度曲线
if TargetTempScanMode:
    Titerationbotton = False
    plotbotton = False
    checkallbutton = False
    specifybotton = False
    save2csvbotton = False
    RandPerfOPbotton=False
    AutoElemTempMarkMode=False

# 根据模式选择要处理的文件
if specifybotton:
    files_to_process = I_elements_list
elif checkallbutton:
    files_to_process = I_elements_list
else:
    files_to_process = [name for name in I_elements_list if name in target_files]

if __name__ == '__main__':
    # 稀土元素置信度导出设置
    RAREEARTH_FIXED_ORDER = ['Y', 'Eu', 'Lu', 'Er', 'Ho', 'Yb', 'La', 'Tm','Tb', 'Sm', 'Pr', 'Ce', 'Nd', 'Dy', 'Gd']
    confidence_csv_path = os.path.join(target_path, 'rareearth_confidence_results.csv')
    confidence_rows = []

    #文件选择
    if not files_to_process:
        print(f"未找到待处理文件，target_files={target_files}")


    for I_element_name in files_to_process:
        
        csv_path = os.path.join(target_path, I_element_name + ".csv")
        x, intensity_sum = load_spectrum_xy(csv_path)
        if x is None:
            print(f"跳过非光谱或无效文件: {I_element_name}.csv")
            continue
        
        signal = intensity_sum
        true_peak_idx, peak_wl, peak_int = wavelet_peak_detection(signal,x,wavelet='mexh', scales=np.arange(1, 11), neighbor=4, min_length=3, coeffi_threshold=700, window=5)#峰值校正

        #温度迭代算法
        if Titerationbotton:
            db_temperature=T_initial
            print(f"正在进行温度迭代算法，初始温度: {db_temperature:.2f} K")
            T_iteration_result= T_iteration(
                    signal,
                    x,
                    T_initial=T_initial,
                    max_iterations=12,
                    tolerance=1e-5,
                    candidate_mode='alterable',
                    t_min=5000,
                    t_max=20000.0,
                    multistart_count=10,
                    alpha=0.35,
                    top_k=3,
                )
            db_temperature=T_iteration_result[0]
        else:
            db_temperature=T_initial
        print(f"迭代得到的电子温度: {db_temperature:.2f} K")
        
        #基体元素检测 
        elements_main,elements_main_list=elements_database_pt2(folder_path,db_temperature) 
        particle_main,elements_main,elements_T_main,elements_R2_main,elements_confidence_main=compute_element_confidence_shape(elements_main, peak_wl, peak_int,x,intensity_sum,
                                                                                            scope=0.2,plot=plotbotton,target=plottarget)
        # print(elements_confidence_main)
        
        
        #特定元素电子温度扫描
        if TargetTempScanMode:
            print(
                color_text(
                    f"\n[{I_element_name}] 启动目标元素温度扫描模式: 元素={scan_target_element}, "
                    f"温度范围={scan_t_min}-{scan_t_max} K, 步长={scan_t_step} K",
                    BLUE,
                )
            )
            scan_T, scan_conf = scan_target_element_confidence(
                peak_wl,
                peak_int,
                x,
                intensity_sum,
                scan_target_element,
                elements_confidence_main=elements_confidence_main,
                t_min=scan_t_min,
                t_max=scan_t_max,
                t_step=scan_t_step,
            )

            #输出显示部分
            best_idx = int(np.argmax(scan_conf)) if scan_conf.size > 0 else -1
            min_idx = int(np.argmin(scan_conf)) if scan_conf.size > 0 else -1
            if best_idx >= 0:
                print(
                    color_text(
                        f"[{I_element_name}] {scan_target_element} 最大置信度={scan_conf[best_idx]:.4f}, "
                        f"对应温度={scan_T[best_idx]:.2f} K",
                        GREEN,
                    )
                )
            if min_idx >= 0:
                print(
                    color_text(
                        f"[{I_element_name}] {scan_target_element} 最小置信度={scan_conf[min_idx]:.4f}, "
                        f"对应温度={scan_T[min_idx]:.2f} K",
                        YELLOW,
                    ))
                print(
                                       color_text(
                        f"[{I_element_name}] {scan_target_element} 置信度差值={scan_conf[best_idx] - scan_conf[min_idx]:.4f}, "
                            f"温度差值={scan_T[best_idx] - scan_T[min_idx]:.2f} K",
                        BLUE,
                    )
                )
                

            plt.figure(figsize=(7, 5))
            plt.plot(
                scan_T,
                scan_conf,
                color='tab:blue',
                linewidth=2.2,
                marker='o',
                label=f'{scan_target_element} Confidence',
            )

            for spine in plt.gca().spines.values():
                spine.set_linewidth(1.8)
            for label in plt.gca().get_xticklabels():
                label.set_fontweight("semibold")
            for label in plt.gca().get_yticklabels():
                label.set_fontweight("semibold")

            plt.xlabel('Temperature (K)', fontsize=15, fontweight="semibold")
            plt.ylabel('Confidence', fontsize=15, fontweight="semibold")
            plt.title(f'{I_element_name} - {scan_target_element} Confidence vs Temperature', fontsize=15, fontweight="semibold")

            plt.tick_params(axis='both', which='major', direction='in', top=True, right=True, width=2.0, length=6, labelsize=12)
            plt.tick_params(axis='both', which='minor', direction='in', top=True, right=True, width=2.0, length=6, labelsize=12)
            plt.grid(alpha=0.3)

            # 温度参考线
            plt.axvline(7500, color='tab:red', linewidth=2.0, linestyle='--', alpha=0.8, label='7500 K')
            plt.axvline(12000, color='tab:red', linewidth=2.0, linestyle='-.', alpha=0.8, label='12000 K')

            plt.legend(loc="upper right", prop={"weight": "semibold", "size": 12}, frameon=False)
            plt.tight_layout()
            plt.show()
            continue

        #基体元素筛选
        elements_rockmain = []
        for elem, conf in elements_confidence_main.items():
            if conf>0.3: #置信度阈值
                elements_rockmain.append(elem)
    
        #elements_database_line_switch header=1
        elements_rareearth,elements_rareearth_list=elements_database_lineswitch(folder_path2,db_temperature,elements_rockmain,LineSwitchMode=True) 
        particle_result,elements_result,elements_T,elements_R2,elements_confidence,elements_line_payload=compute_element_confidence_shape(elements_rareearth, peak_wl, peak_int,x,intensity_sum,
                                                                                                    scope=0.2,plot=plotbotton,target=plottarget,
                                                                                                    return_line_payload=True)
            
        #置信度0元素筛选
        coarse_elements_result = elements_result.copy()
        coarse_elements_T = elements_T.copy()
        coarse_elements_R2 = elements_R2.copy()
        coarse_elements_confidence = elements_confidence.copy()
        
        #置信度为0的元素提取
        zero_conf_elements = [
            elem
            for elem, conf in coarse_elements_confidence.items()
            if float(conf) <=0.01
        ]
        
        coarse_matched_refit_elements = [
            elem
            for elem in zero_conf_elements
            if float(coarse_elements_T.get(elem, 0.0)) > 0.0
            and float(coarse_elements_R2.get(elem, 0.0)) > 0.0
        ]
        
        #已经匹配了谱线的元素直接多峰拟合
        coarse_matched_fit_lines = build_coarse_matched_fit_lines(
            elements_line_payload,
            coarse_matched_refit_elements,
        )
        if not coarse_matched_fit_lines.empty:
            print(color_text(
                "粗检测有有效 T/R2 但置信度为 0 的元素，将使用粗检测已匹配谱线进行多峰拟合:",
                GREEN,
            ))
            print(coarse_matched_fit_lines.to_string(index=False))
        
        
  
        allowed_main_elements = {"TI", "K", "NA", "MG", "CA", "SI", "FE", "AL","MN"}
        main_elements_normalized = {
            normalized
            for m in elements_rockmain
            for normalized in [str(m).strip().upper()]
            if normalized in allowed_main_elements
        }
        # print(main_elements_normalized)



        #多峰拟合调用
        target_fit_params = MultiPeakFit(
            folder_path2,
            main_elements_normalized,
            elements_line_payload,
            target_base_elements=zero_conf_elements,
            target_fit_lines=coarse_matched_fit_lines,
        )
        
        if not target_fit_params.empty:
            print(color_text("\nwl_tofit 目标峰拟合结果:", GREEN))
            print(target_fit_params.to_string(index=False))

            elements_rareearth_refit, _ = elements_database_lineswitch(
                folder_path2,
                db_temperature,
                elements_rockmain,
                LineSwitchMode=False,
                IncludeMatrixPureLinesMode=True,
            )
            rescue_rows = []

            
            #rescue_elem为代拟合元素
            for rescue_elem in zero_conf_elements:

                rescue_fit_params = target_fit_params.loc[
                    target_fit_params["BaseElement"].astype(str).str.upper() == str(rescue_elem).upper()
                ].copy()
                if rescue_fit_params.empty:
                    continue

                rescue_elements = filter_elements_by_base(elements_rareearth_refit, [rescue_elem])
                if not rescue_elements:
                    continue

                corrected_peak_wl, corrected_peak_int = append_fitted_peak_candidates(
                    peak_wl,
                    peak_int,
                    rescue_fit_params,
                )
                
                

                (
                    _rescue_match_results,
                    rescue_results,
                    rescue_T,
                    rescue_R2,
                    rescue_confidence,
                ) = compute_element_confidence_shape(
                    rescue_elements,
                    corrected_peak_wl,
                    corrected_peak_int,
                    x,
                    intensity_sum,
                    scope=0.2,
                    plot=plotbotton and str(rescue_elem).strip().upper() == str(target_element).strip().upper(),
                    target="PrII",
                )

                if rescue_elem not in rescue_confidence:
                    continue

                old_conf = float(coarse_elements_confidence.get(rescue_elem, 0.0))
                new_conf = float(rescue_confidence.get(rescue_elem, 0.0))
                elements_confidence[rescue_elem] = new_conf
                if rescue_elem in rescue_results:
                    elements_result[rescue_elem] = rescue_results[rescue_elem]
                if rescue_elem in rescue_T:
                    elements_T[rescue_elem] = rescue_T[rescue_elem]
                if rescue_elem in rescue_R2:
                    elements_R2[rescue_elem] = rescue_R2[rescue_elem]

                rescue_rows.append({
                    "Element": rescue_elem,
                    "CoarseConfidence": old_conf,
                    "RefitConfidence": new_conf,
                    "RefitT": float(rescue_T.get(rescue_elem, 0.0)),
                    "RefitR2": float(rescue_R2.get(rescue_elem, 0.0)),
                    "FitPeakCount": int(len(rescue_fit_params)),
                })

            if rescue_rows:
                rescue_df = pd.DataFrame(rescue_rows)
                print(color_text("\n粗置信度为 0 的元素多峰拟合补救结果:", GREEN))
                print(rescue_df.to_string(index=False))
            



        # 对有置信度的元素做温度扫描，若置信度波动超过阈值则在最终输出中标注
        temp_sensitive_marks = {}
        if AutoElemTempMarkMode:
            print(color_text(f"\n[{I_element_name}] 启动自动温度敏感元素标注算法，扫描置信度≥{auto_mark_conf_min}的R2=1的特殊元素", BLUE))
            # candidate_scan_elems = [
            #     elem for elem, conf in elements_confidence.items()
            #     if float(conf) >= auto_mark_conf_min and float(elements_R2.get(elem, 0.0)) == 1.0
            # ]
            # print(f"候选扫描元素: {candidate_scan_elems}")
            allowed_elems = {"La", "Yb", "Tb", "Eu", "Er"}
            candidate_scan_elems = [
                elem for elem, conf in elements_confidence.items()
                if elem in allowed_elems and float(elements_R2.get(elem, 0.0)) == 1.0
            ]
            for scan_elem in candidate_scan_elems:
                scan_T_elem, scan_conf_elem = scan_target_element_confidence(
                    peak_wl,
                    peak_int,
                    x,
                    intensity_sum,
                    scan_elem,
                    elements_confidence_main=elements_confidence_main,
                    t_min=scan_t_min,
                    t_max=scan_t_max,
                    t_step=scan_t_step,
                )
                if scan_conf_elem.size == 0:
                    continue

                best_idx_elem = int(np.argmax(scan_conf_elem))
                min_idx_elem = int(np.argmin(scan_conf_elem))
                
                
            #极值勘误部分
                best_t = float(scan_T_elem[best_idx_elem])
                if best_t < 7450 or best_t > 12100:
                    temp_sensitive_marks[scan_elem] = {
                        'delta_conf': 1,
                        'best_t': best_t,
                        'min_t': float(scan_T_elem[min_idx_elem]),
                        'delta_p': float(1),
                        'delta_conf_cal': float(1)
                    }
                    
            # #浮动阈值勘误部分-----施工中
            #     payload_key = f"{scan_elem}II"
            #     payload = elements_line_payload.get(payload_key, {})
            #     # print(payload)
                
            #     wl_sel = np.asarray(payload.get('wl', []), dtype=float)
            #     A_sel = np.asarray(payload.get('A', []), dtype=float)
            #     E_sel = np.asarray(payload.get('E', []), dtype=float)
            #     g_sel = np.asarray(payload.get('g', []), dtype=float)
            #     matched_idx_sel = np.asarray(payload.get('matched_theo_idx', []), dtype=int)
            #     # if scan_elem=='Yb':
            #     #     print(wl_sel, A_sel, E_sel, g_sel, matched_idx_sel)

            #     if wl_sel.size == 0 or A_sel.size == 0 or E_sel.size == 0 or g_sel.size == 0:
            #         continue

            #     p_best = rel_intensity(wl_sel, A_sel, E_sel, g_sel, float(scan_T_elem[best_idx_elem]))
            #     p_min = rel_intensity(wl_sel, A_sel, E_sel, g_sel, float(scan_T_elem[min_idx_elem]))
                
            #     delta_conf = float(np.max(scan_conf_elem) - np.min(scan_conf_elem))
                
            #     if matched_idx_sel.size > 0:
            #         # delta_p = float(np.sum(np.abs(p_best[matched_idx_sel] - p_min[matched_idx_sel])))
            #         delta_p = float(np.max(np.abs(p_best - p_min)))
            #         delta_conf_cal=1-np.exp(-(np.sum((p_best-p_min)**2))*len(matched_idx_sel)*4.5) #根据概率差值计算置信度差值
            #     else:
            #         delta_p = 0.0
            #         delta_conf_cal = 0.0
                    
            #     if delta_conf >=0.8:
            #         temp_sensitive_marks[scan_elem] = {
            #             'delta_conf': delta_conf,
            #             'best_t': float(scan_T_elem[best_idx_elem]),
            #             'min_t': float(scan_T_elem[min_idx_elem]),
            #             'delta_p': float(delta_p),
            #             'delta_conf_cal': float(delta_conf_cal)
            #         }
            #     else:
            #         if delta_conf>(delta_conf_cal*1.3):
            #             temp_sensitive_marks[scan_elem] = {
            #                 'delta_conf': delta_conf,
            #                 'best_t': float(scan_T_elem[best_idx_elem]),
            #                 'min_t': float(scan_T_elem[min_idx_elem]),
            #                 'delta_p': float(delta_p),
            #                 'delta_conf_cal': float(delta_conf_cal)
            #             }

                # #固定阈值0.8勘误
                # #计算置信度delta
                # delta_conf = float(np.max(scan_conf_elem) - np.min(scan_conf_elem))
                # # if delta_conf >= auto_mark_delta_threshold:
                # if delta_conf >= 0.8:
                #     temp_sensitive_marks[scan_elem] = {
                #         'delta_conf': delta_conf,
                #         'best_t': float(scan_T_elem[best_idx_elem]),
                #         'min_t': float(scan_T_elem[min_idx_elem]),
                #         'delta_p': float(delta_conf),
                #         'delta_conf_cal': 0
                #     }


        # 记录当前光谱的稀土元素置信度（固定列顺序）
        if save2csvbotton:
            row = {'spectrum_name': I_element_name}
            for elem in RAREEARTH_FIXED_ORDER:
                conf_value = float(elements_confidence.get(elem, 0.0))
                # 如果元素被标记为温度敏感，则将其置信度设为0以突出显示（或根据需要调整）
                if elem in temp_sensitive_marks:
                    conf_value = 0.0
                row[elem] = round(conf_value, 4)
            row['iter_temperature'] = round(float(db_temperature), 4)
            confidence_rows.append(row)

        #print结果展示
        if printbotton:
            print("\n---" ,I_element_name, "---") 
            print("--- Before 多峰补救：元素层面（距离 + 置信度） ---")
            sorted_elems_before = sorted(coarse_elements_result.keys(), key=lambda x: coarse_elements_result[x])

            if specifybotton:
                for elem in sorted_elems_before:
                    if elem != target_element:
                        continue
                    dist = coarse_elements_result.get(elem, np.nan)
                    conf = coarse_elements_confidence.get(elem, 0)
                    elem_T = coarse_elements_T.get(elem, 0)
                    R2 = coarse_elements_R2.get(elem, 0)
                    temp_text = color_text(f"温度={elem_T:<8.4f}", BLUE)
                    r2_text = color_text(f"R2 = {R2:<8.4f}", YELLOW)
                    conf_text = color_text(f"置信度 = {conf:<8.4f}", GREEN)
                    print(f"{elem:<6s} 平均距离 = {dist:<8.4f} | {temp_text} | {r2_text} | {conf_text}")
                    break
            else:
                for elem in sorted_elems_before:
                    dist = coarse_elements_result.get(elem, np.nan)
                    conf = coarse_elements_confidence.get(elem, 0)
                    elem_T = coarse_elements_T.get(elem, 0)
                    R2 = coarse_elements_R2.get(elem, 0)
                    temp_text = color_text(f"温度={elem_T:<8.4f}", BLUE)
                    r2_text = color_text(f"R2 = {R2:<8.4f}", YELLOW)
                    conf_text = color_text(f"置信度 = {conf:<8.4f}", GREEN)
                    print(f"{elem:<6s} 平均距离 = {dist:<8.4f} | {temp_text} | {r2_text} | {conf_text}")

            # 元素+置信度 
            print("--- After 多峰补救：元素层面（距离 + 置信度） ---")
            sorted_elems = sorted(elements_result.keys(), key=lambda x: elements_result[x])

            #输出显示部分
            if specifybotton:
                for elem in sorted_elems:
                    if elem != target_element:
                        continue
                    dist = elements_result.get(elem, np.nan)
                    conf = elements_confidence.get(elem, 0)
                    elem_T = elements_T.get(elem, 0)
                    R2 = elements_R2.get(elem, 0)
                    temp_text = color_text(f"温度={elem_T:<8.4f}", BLUE)
                    r2_text = color_text(f"R2 = {R2:<8.4f}", YELLOW)
                    conf_text = color_text(f"置信度 = {conf:<8.4f}", GREEN)
                    sensitivity_mark = ""
                    if elem in temp_sensitive_marks:
                        mark = temp_sensitive_marks[elem]
                        sensitivity_mark = color_text(
                            f" [温度敏感 ΔC={mark['delta_conf']:.3f}, {mark['min_t']:.0f}K->{mark['best_t']:.0f}K, ΔP={mark['delta_p']:.3f}]",
                            YELLOW,
                        )
                    print(f"{elem:<6s} 平均距离 = {dist:<8.4f} | {temp_text} | {r2_text} | {conf_text}{sensitivity_mark}")
                    break
            else:
                for elem in sorted_elems:
                    # if elements_R2.get(elem, 0) == 1.0 and float(elements_confidence.get(elem, 0)) > 0.05:
                        dist = elements_result.get(elem, np.nan)
                        conf = elements_confidence.get(elem, 0)
                        elem_T = elements_T.get(elem, 0)
                        R2 = elements_R2.get(elem, 0)
                        temp_text = color_text(f"温度={elem_T:<8.4f}", BLUE)
                        r2_text = color_text(f"R2 = {R2:<8.4f}", YELLOW)
                        conf_text = color_text(f"置信度 = {conf:<8.4f}", GREEN)
                        sensitivity_mark = ""
                        if elem in temp_sensitive_marks:
                            mark = temp_sensitive_marks[elem]
                            sensitivity_mark = color_text(
                                f" [温度敏感 ΔC={mark['delta_conf']:.3f}, {mark['min_t']:.0f}K->{mark['best_t']:.0f}K, ΔP={mark['delta_p']:.3f}], ΔC_cal={mark['delta_conf_cal']:.3f}",
                                YELLOW,
                            )
                        print(f"{elem:<6s} 平均距离 = {dist:<8.4f} | {temp_text} | {r2_text} | {conf_text}{sensitivity_mark}")


    # 批量结果导出到CSV：第一列为光谱名，后续为固定顺序稀土元素置信度
    if confidence_rows:
        output_columns = ['spectrum_name'] + RAREEARTH_FIXED_ORDER + ['iter_temperature']
        confidence_df = pd.DataFrame(confidence_rows, columns=output_columns)
        confidence_df.to_csv(confidence_csv_path, index=False, encoding='utf-8-sig', float_format='%.4f')
        print(color_text(f"\n已导出稀土元素置信度到 CSV: {confidence_csv_path}", GREEN))

    #随机光谱性能测试，在随机光谱路径处设置(target_path)
    if RandPerfOPbotton:
        RandSepc_PerforOP(target_path)


