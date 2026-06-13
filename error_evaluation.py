#此文件用来衡量计算得出温度的误差容许范围
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

kB=8.617330350e-5 #eV/K


def read_csv_with_fallback(file_path, header=0, encodings=None):
    """按编码顺序尝试读取 CSV，失败则继续尝试下一个编码。"""
    if encodings is None:
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb18030', 'latin1']

    last_error = None
    for enc in encodings:
        try:
            return pd.read_csv(file_path, header=header, encoding=enc, on_bad_lines='skip')
        except UnicodeDecodeError as e:
            last_error = e
        except Exception as e:
            last_error = e

    raise ValueError(f'无法读取文件: {file_path}。尝试编码: {encodings}。最后错误: {last_error}')

file_path = r'D:\LIBS\RREdetectation\Elements_database\MgI.csv'
df_raw = read_csv_with_fallback(file_path, header=1)
# file_path = r'D:\LIBS\RREdetectation\Rareearth_pt3\YII.csv'
# df_raw = read_csv_with_fallback(file_path, header=0)

df = df_raw.copy()

df = df.iloc[1::2].copy()

# 第9列若为 N，则该行不参与后续读取与计算
if df.shape[1] >= 9:
    col9 = df.iloc[:, 8]
    keep_mask = col9.isna() | (col9.astype(str).str.strip().str.upper() != 'N')
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



def error_evaluation(T_calculated,T_true):
    error = np.abs(rel_intensity(wl,A,E,g,T_calculated) - rel_intensity(wl,A,E,g,T_true))
    confidence_error=np.exp(-1.5*np.sum(error**2)/0.6)
    return confidence_error


def plot_confidence_error_curve(T_true=10000, t_min=5000, t_max=20000, num=500, save_path='confidence_error_curve.png'):
    """绘制 T_calculated 在指定区间内时 confidence_error 的变化曲线。"""
    T_values = np.linspace(t_min, t_max, num)
    confidence_mean = np.zeros(num)

    for i, T_calculated in enumerate(T_values):
        confidence_mean[i] = error_evaluation(T_calculated, T_true)

    plt.figure(figsize=(7, 5))
    plt.plot(T_values, confidence_mean, color='tab:blue', linewidth=2.2, label='Confidence')

    for spine in plt.gca().spines.values():
        spine.set_linewidth(1.8)
    for label in plt.gca().get_xticklabels():
        label.set_fontweight("semibold")
    for label in plt.gca().get_yticklabels():
        label.set_fontweight("semibold")

    plt.axvline(T_true, color='tab:red', linestyle='--', linewidth=2, alpha=0.8, label=f'T-Ref={T_true}')

    plt.xlabel('T', fontsize=15, fontweight="semibold")
    plt.ylabel('Confidence', fontsize=15, fontweight="semibold")
    plt.title('Confidence-T', fontsize=15, fontweight="semibold")

    plt.grid(alpha=0.3)
    

    plt.tick_params(axis='both', which='major', direction='in', top=True, right=True,width=2.0, length=6, labelsize=12)
    plt.tick_params(axis='both', which='minor', direction='in', top=True, right=True,width=2, length=6,labelsize=12)


    plt.legend(loc="upper right", prop={"weight": "semibold", "size": 12}, frameon=False)
    plt.tight_layout() 
    plt.show()

def plot_p_T_curve(T_true=10000, t_min=5000, t_max=20000, num=500):
    T_values = np.linspace(t_min, t_max, num)
    p_T_values = np.zeros((len(wl), num))
    for i, T in enumerate(T_values):
        p_T_values[:, i] = rel_intensity(wl, A, E, g, T)
    plt.figure(figsize=(7, 5))
    for i in range(len(wl)):
        plt.plot(T_values, p_T_values[i, :], label=f'wl={wl[i]:.1f}nm', linewidth=2.2)
    plt.axvline(T_true, color='tab:red', linestyle='--', linewidth=2,alpha=0.8, label=f'T_true={T_true}')

    plt.tick_params(axis='both', which='major', direction='in', top=True, right=True,length=6, width=2.0, labelsize=12)

    for spine in plt.gca().spines.values():
        spine.set_linewidth(1.8)
    for label in plt.gca().get_xticklabels():
        label.set_fontweight("semibold")
    for label in plt.gca().get_yticklabels():
        label.set_fontweight("semibold")

    plt.xlabel('T',fontsize=15, fontweight="semibold")
    plt.ylabel('P', fontsize=15, fontweight="semibold")
    plt.title('P-T Curve', fontsize=15, fontweight="semibold")

    # plt.legend(prop={"weight": "semibold", "size": 12},frameon=False)
    plt.tight_layout()
    plt.show()


def derivative_curve_value(wl,A,E,g,i,T):
    """独立于 derivative_P_T 的可绘图导数指标：mean(|d(lnp)/dT|)。"""
    if T <= 0:
        return 0.0
    p = rel_intensity(wl, A, E, g, T)
    E_mean = np.sum(E * p)

    dp_dT = (E[i] - E_mean) / (kB * T**2)
    return dp_dT

def plot_derivative_vs_T(wl,A,E,g,k, T_true, t_min=500, t_max=20000, num=2000, save_path='derivative_vs_T.png', mode='single'):
    """绘制导数指标随温度 T 的变化曲线。

    mode='single': 仅绘制 wl[k] 对应的一条导数线。
    mode='all': 绘制 wl 全部谱线对应的导数线。
    """
    T_values = np.linspace(t_min, t_max, num)
    mode = str(mode).strip().lower()

    plt.figure(figsize=(7, 5))

    if mode == 'single':
        if not (0 <= k < len(wl)):
            raise IndexError(f'k 越界: {k}, 有效范围为 [0, {len(wl) - 1}]。')

        y_values = np.zeros(num, dtype=float)
        print(wl[k])
        for i, T in enumerate(T_values):
            y_values[i] = derivative_curve_value(wl, A, E, g, k, T)
        plt.plot(T_values, y_values, color='tab:green', linewidth=2, label=f'wl={wl[k]:.1f}nm')

    elif mode == 'all':
        for line_idx in range(len(wl)):
            y_values = np.zeros(num, dtype=float)
            for i, T in enumerate(T_values):
                y_values[i] = derivative_curve_value(wl, A, E, g, line_idx, T)
            plt.plot(T_values, y_values, linewidth=2, alpha=0.85, label=f'wl={wl[line_idx]:.1f}nm')

    else:
        raise ValueError("mode 仅支持 'single' 或 'all'。")

    plt.axvline(T_true, color='tab:red', linestyle='--', linewidth=2, label=f'T_true={T_true}')
    plt.xlabel('T(K)',fontsize=15, fontweight="semibold")
    plt.ylabel('Derivative Indicator', fontsize=15, fontweight="semibold")
    # plt.title('Derivative vs Temperature', fontsize=20, fontweight="semibold")

    for spine in plt.gca().spines.values():
        spine.set_linewidth(1.8)

    for label in plt.gca().get_xticklabels():
        label.set_fontweight("semibold")
    for label in plt.gca().get_yticklabels():
        label.set_fontweight("semibold")



    plt.tick_params(axis='both', which='major', direction='in', top=True, right=True,length=6, width=2.0, labelsize=12)

    plt.grid(False)
    if mode == 'single' or len(wl) <= 20:
        plt.legend(loc="upper right", prop={"weight": "semibold", "size": 12}, frameon=False)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.show()




def plot_U_sum_vs_T_from_df(
    df_input,
    t_min=500,
    t_max=20000,
    num=2000,
    save_path='U_sum_vs_T_from_df.png',
    show_plot=True,
    return_values=False
):
    """按输入 df 的前四列规则过滤后，绘制 U_sum 随 T 的变化。"""
    def parse_numeric(value):
        """将数值或文本数值转换为 float；无法转换则返回 NaN。"""
        if pd.isna(value):
            return np.nan

        if isinstance(value, (int, float, np.integer, np.floating)):
            return float(value)

        text = str(value).strip()
        if text == '':
            return np.nan

        text_upper = text.upper()
        if text_upper in {'#VALUE!', 'NAN', 'NONE', 'NULL'}:
            return np.nan

        # 处理类似 "70 314.624" 的文本数字
        cleaned = text.replace(' ', '').replace('\u3000', '')
        try:
            return float(cleaned)
        except ValueError:
            return np.nan

    rows = []
    total_rows = len(df_input)
    skipped_rows = 0

    for _, row in df_input.iterrows():
        wl_raw = parse_numeric(row.iloc[0])
        A_raw = parse_numeric(row.iloc[1])
        E_raw = parse_numeric(row.iloc[2])
        g_raw = parse_numeric(row.iloc[3])

        # 只要四个量中有一个缺失/非法，该行就跳过
        if not (np.isfinite(wl_raw) and np.isfinite(A_raw) and np.isfinite(E_raw) and np.isfinite(g_raw)):
            skipped_rows += 1
            continue
        

        #文件中NIST的数值
        wl_val = float(wl_raw) * 0.1
        A_val = float(A_raw)*1e-8
        E_val = float(E_raw) * 1.2398e-4
        g_val = float(g_raw) * 2.0 + 1.0
 
        #注意：此处变换了，不是文件里面的数值了，直接用global的谱线数值
        rows.append((wl_val, A_val, E_val, g_val))

    if len(rows) == 0:
        raise ValueError('过滤后没有可用数据，无法计算 U_sum。请检查 df 前四列是否包含有效数值。')

    print(f'原始行数: {total_rows}, 有效行数: {len(rows)}, 跳过行数: {skipped_rows}')

    filtered = np.array(rows, dtype=float)
    g_local = filtered[:, 3]
    A_local = filtered[:, 1]
    E_local = filtered[:, 2]

    T_values = np.linspace(t_min, t_max, num)
    U_sum_values = np.zeros(num, dtype=float)

    for i, T in enumerate(T_values):
        _, U_sum_values[i] = U_Calculate(g_local, A_local, E_local, T)

    if show_plot:
        plt.figure(figsize=(9, 5))
        plt.plot(T_values, U_sum_values, color='tab:orange', linewidth=2, label='U_sum(T) from df')
        plt.xlabel('T')
        plt.ylabel('U_sum')
        plt.title('U_sum vs Temperature (from filtered df)')
        plt.minorticks_on()
        plt.tick_params(axis='both', which='major', direction='in', top=True, right=True)
        plt.tick_params(axis='both', which='minor', direction='in', top=True, right=True)
        plt.grid(alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig(save_path, dpi=300)
        plt.show()

    if return_values:
        return T_values, U_sum_values


def plot_dU_sum_dT_vs_T_from_df(df_input, t_min=500, t_max=20000, num=2000, save_path='dU_sum_dT_vs_T_from_df.png'):
    """绘制 dU_sum/dT 随温度 T 的变化曲线。"""
    T_values, U_sum_values = plot_U_sum_vs_T_from_df(
        df_input,
        t_min=t_min,
        t_max=t_max,
        num=num,
        show_plot=False,
        return_values=True
    )

    dU_dT_values = np.gradient(U_sum_values, T_values)

    plt.figure(figsize=(9, 5))
    plt.plot(T_values, dU_dT_values, color='tab:purple', linewidth=2, label='dU_sum/dT')
    plt.xlabel('T')
    plt.ylabel('dU_sum/dT')
    # plt.title('dU_sum/dT vs Temperature (from filtered df)')
    plt.minorticks_on()
    plt.tick_params(axis='both', which='major', direction='in', top=True, right=True)
    plt.tick_params(axis='both', which='minor', direction='in', top=True, right=True)
    plt.grid(alpha=0.3)
    plt.legend(loc="upper right", prop={"weight": "semibold", "size": 12}, frameon=False)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.show()


def plot_two_exponentials(x_min=0, x_max=5, num=500, save_path='exp_compare.png'):
    """按当前脚本风格绘制 exp(-1.5x) 与 exp(-2x) 的对比曲线。"""
    x = np.linspace(x_min, x_max, num)
    y1 = np.exp(-1.5 * x)
    y2 = np.exp(-4.5 * x)

    plt.figure(figsize=(7, 5))
    plt.plot(x, y1, color='tab:blue', linewidth=2.2, label='exp(-1.5x)')
    plt.plot(x, y2, color='tab:red', linewidth=2.2, linestyle='--', label='exp(-2x)')

    for spine in plt.gca().spines.values():
        spine.set_linewidth(1.8)
    for label in plt.gca().get_xticklabels():
        label.set_fontweight("semibold")
    for label in plt.gca().get_yticklabels():
        label.set_fontweight("semibold")

    plt.xlabel('X', fontsize=15, fontweight="semibold")
    plt.ylabel('Y', fontsize=15, fontweight="semibold")
    plt.title('Exponential Curves', fontsize=15, fontweight="semibold")

    plt.tick_params(axis='both', which='major', direction='in', top=True, right=True, width=2.0, length=6, labelsize=12)
    plt.tick_params(axis='both', which='minor', direction='in', top=True, right=True, width=2.0, length=6, labelsize=12)
    plt.grid(alpha=0.3)

    plt.legend(loc="upper right", prop={"weight": "semibold", "size": 12}, frameon=False)
    plt.tight_layout()
    plt.show()


def Intensity_Factor(A,g,E,T):
    """计算强度因子 A*g*exp(-E/(kB*T))，并处理可能的数值问题。"""
    if T <= 0:
        return np.zeros_like(A)
    factor = A * g *(-E)*np.exp(-E / (kB * T))
    denominator = A*g*np.exp(-E / (kB * T))
    factor=factor/np.sum(denominator)

    # print(factor)
    # print(denominator)
    # print(E)
    # print(np.mean(E))
    # print(np.std(E))
    print(E-np.sum(factor))
    return factor

# 测试单个点的导数计算
# print(E[1])
# print(derivative_P_T(1, 10000))

# plot_derivative_vs_T(wl, A, E, g, 0, T_true=10000, t_min=1000, t_max=20000, num=2000, mode='all')
# plot_confidence_error_curve(T_true=10000, t_min=5000, t_max=20000, num=500)
# plot_p_T_curve(T_true=10000, t_min=5000, t_max=20000, num=500)



#第二部分理论开发
#配分函数
# df_raw = read_csv_with_fallback(r'D:\LIBS\RREdetectation\Ucalculation\0406_FeI.csv', header=0)
# plot_U_sum_vs_T_from_df(df_raw, t_min=1000, t_max=20000, num=2000)
# plot_dU_sum_dT_vs_T_from_df(df_raw, t_min=1000, t_max=20000, num=2000)

#第三部分开发强度因子
# Intensity_Factor(A, g, E, T=10000)


# plot_two_exponentials(x_min=0, x_max=5, num=500)

