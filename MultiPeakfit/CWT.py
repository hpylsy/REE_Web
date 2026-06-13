import numpy as np
import scipy.signal as signal
import scipy.ndimage as ndi
import matplotlib.pyplot as plt
import pandas as pd
from scipy.optimize import least_squares, minimize

signal_path=r'D:\LIBS\RREdetectation\MultiPeakfit\4_24data.csv'
data=pd.read_csv(signal_path,header=0,encoding="gbk")

wl=data.iloc[:,0]
rel_int=data.iloc[:,1]
wl=pd.to_numeric(wl, errors='coerce')
rel_int=pd.to_numeric(rel_int, errors='coerce')

valid_mask=wl.notna() & rel_int.notna()
wl=wl[valid_mask]
rel_int=rel_int[valid_mask]
wl = wl.reset_index(drop=True)
rel_int = rel_int.reset_index(drop=True)

def mexican_hat_wavelet(points, a):

    A = 2 / (np.sqrt(3 * a) * (np.pi**0.25))
    wsq = a**2
    x = np.linspace(-points//2, points//2, points)
    return A * (1 - x**2/wsq) * np.exp(-x**2/(2*wsq))


def cwt_second_derivative(signal_data, scale):
    n = len(signal_data)
    points = min(200, n)
    if points < 3:
        points = 3
    if points % 2 == 0:
        points -= 1

    wavelet = mexican_hat_wavelet(points=points, a=scale)
    cwt = np.convolve(signal_data, wavelet, mode='same')
    return cwt

def find_peaks_from_second_derivative(cwt_data, threshold=0.01):

    minima = signal.argrelextrema(cwt_data, np.less)[0]

    min_val = np.min(cwt_data)
    selected = [i for i in minima if abs(cwt_data[i]) > threshold * abs(min_val)]

    return np.array(selected, dtype=int)

def remove_edge_artifacts(cwt_data, minima_indices):

    maxima_indices = signal.argrelextrema(cwt_data, np.greater)[0]
    valid_minima = []

    for i, m in enumerate(minima_indices):
        left_max = maxima_indices[maxima_indices < m]
        # 找右侧最近极大值
        right_max = maxima_indices[maxima_indices > m]

        has_left = len(left_max) > 0
        has_right = len(right_max) > 0

        # 判断是否为边界伪峰
        if i == 0:
            # 第一个极小值：必须有左极大值
            if not has_left:
                continue

        if i == len(minima_indices) - 1:
            # 最后一个极小值：必须有右极大值
            if not has_right:
                continue

        # 中间的极小值默认保留（论文假设artifact只在边界）
        valid_minima.append(m)
    return np.array(valid_minima)

def estimate_fwhm(cwt_data, peak_indices, wavelength):
    fwhm_list = []
    cwt_data = np.asarray(cwt_data, dtype=float)
    wavelength = np.asarray(wavelength, dtype=float)
    n = min(cwt_data.size, wavelength.size)
    if n == 0:
        return np.array(fwhm_list)

    cwt_data = cwt_data[:n]
    wavelength = wavelength[:n]
    peak_indices = np.asarray(peak_indices, dtype=int)
    peak_indices = peak_indices[(peak_indices >= 0) & (peak_indices < n)]

    for idx in peak_indices:
        # 左侧最大值
        left = idx
        while left > 1 and cwt_data[left-1] > cwt_data[left]:
            left -= 1
        # 右侧最大值
        right = idx
        while right < len(cwt_data)-2 and cwt_data[right+1] > cwt_data[right]:
            right += 1
        delta_x = abs(wavelength[right] - wavelength[left])
        fwhm = 0.7 * delta_x   # 论文FWHM经验公式
        fwhm_list.append(fwhm)
    return np.array(fwhm_list)



def cwt_peak_detection(wavelength, intensity, scale=1, threshold=0.01):
    cwt_data = cwt_second_derivative(intensity, scale)
    peaks = find_peaks_from_second_derivative(cwt_data, threshold)
    
    peaks = remove_edge_artifacts(cwt_data, peaks)
    fwhm = estimate_fwhm(cwt_data, peaks, wavelength)
    return peaks, fwhm, cwt_data



def plot_result(wl, intensity, peaks, cwt_data):
    wl_np = np.asarray(wl, dtype=float)
    intensity_np = np.asarray(intensity, dtype=float)
    peaks = np.asarray(peaks, dtype=int)
    peaks = peaks[(peaks >= 0) & (peaks < len(wl_np))]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8.5, 6.2), sharex=True)

    ax1.plot(wl_np, intensity_np, color='tab:blue', linewidth=1.8, label='Spectrum')
    ax1.scatter(wl_np[peaks], intensity_np[peaks], color='tab:red', s=36, label='Detected Peaks', zorder=5)
    ax1.set_ylabel('Relative Intensity', fontsize=13, fontweight='semibold')
    ax1.set_title('LIBS Spectrum', fontsize=14, fontweight='semibold')
    ax1.grid(alpha=0.3)
    ax1.legend(loc='upper right', prop={'weight': 'semibold', 'size': 11}, frameon=False)

    ax2.plot(wl_np, cwt_data, color='tab:orange', linewidth=1.6, label='CWT (2nd derivative)')
    ax2.scatter(wl_np[peaks], cwt_data[peaks], color='tab:green', s=28, zorder=5, label='Peaks on CWT')
    ax2.set_xlabel('Wavelength (nm)', fontsize=13, fontweight='semibold')
    ax2.set_ylabel('CWT Coeff.', fontsize=13, fontweight='semibold')
    ax2.grid(alpha=0.3)
    ax2.legend(loc='upper right', prop={'weight': 'semibold', 'size': 11}, frameon=False)

    for ax in (ax1, ax2):
        for spine in ax.spines.values():
            spine.set_linewidth(1.8)
        for label in ax.get_xticklabels():
            label.set_fontweight('semibold')
        for label in ax.get_yticklabels():
            label.set_fontweight('semibold')

    plt.tight_layout()
    plt.show()


extrema_idx = []
for i in range(1, len(rel_int) - 1):
    is_local_max = rel_int.iloc[i] > rel_int.iloc[i - 1] and rel_int.iloc[i] > rel_int.iloc[i + 1]
    #is_local_min = rel_int.iloc[i] < rel_int.iloc[i - 1] and rel_int.iloc[i] < rel_int.iloc[i + 1]
    if is_local_max:
        extrema_idx.append(i)

peak_wl = wl.iloc[extrema_idx]
peak_int = rel_int.iloc[extrema_idx]





def gaussian(x, a, mu, sigma):
    return a * np.exp(-((x - mu) ** 2) / (2 * sigma ** 2))


def fit_two_fixed_gaussian_peaks(wl, intensity, peak_indices, cwt_data):
    wl_np = np.asarray(wl, dtype=float)
    intensity_np = np.asarray(intensity, dtype=float)
    peak_indices = np.asarray(peak_indices, dtype=int)
    peak_indices = peak_indices[(peak_indices >= 0) & (peak_indices < len(wl_np))]

    if peak_indices.size < 2:
        return None

    # 取强度最大的两个峰，并按波长从小到大排序
    top2_local = np.argsort(intensity_np[peak_indices])[-2:]
    selected_idx = np.sort(peak_indices[top2_local])

    mu_two = wl_np[selected_idx]
    fwhm_two = estimate_fwhm(np.asarray(cwt_data, dtype=float), selected_idx, wl_np)
    sigma_init = np.maximum(fwhm_two / 2.355, 1e-6)

    amp_upper = np.maximum(intensity_np[selected_idx], 1e-8)
    amp0 = amp_upper * 0.5

    def global_gaussian_rms(params):
        amps = params[:2]
        sigmas = params[2:]
        y_fit = (
            gaussian(wl_np, amps[0], mu_two[0], sigmas[0])
            + gaussian(wl_np, amps[1], mu_two[1], sigmas[1])
        )
        return float(np.sqrt(np.mean((intensity_np - y_fit) ** 2)))

    sigma_lower = np.maximum(sigma_init * 0.2, 1e-6)
    sigma_upper = np.maximum(sigma_init * 5.0, sigma_lower * 1.2)

    x0 = np.concatenate([amp0, sigma_init])
    bounds = [(0.0, float(u)) for u in amp_upper] + [(float(l), float(u)) for l, u in zip(sigma_lower, sigma_upper)]
    
    #Optimization
    result = minimize(
        global_gaussian_rms,
        x0=x0,
        method='L-BFGS-B',
        bounds=bounds,
        options={'maxiter': 20000, 'ftol': 1e-12},
    )

    amps = result.x[:2]
    sigma_two = result.x[2:]
    g1 = gaussian(wl_np, amps[0], mu_two[0], sigma_two[0])
    g2 = gaussian(wl_np, amps[1], mu_two[1], sigma_two[1])
    g_sum = g1 + g2

    return {
        'selected_idx': selected_idx,
        'amps': amps,
        'mu': mu_two,
        'sigma_init': sigma_init,
        'sigma': sigma_two,
        'g1': g1,
        'g2': g2,
        'g_sum': g_sum,
        'success': result.success,
        'message': result.message,
    }


def plot_two_gaussian_fit(wl, intensity, fit_result):
    wl_np = np.asarray(wl, dtype=float)
    intensity_np = np.asarray(intensity, dtype=float)

    plt.figure(figsize=(8.5, 5.2))
    plt.plot(wl_np, intensity_np, color='tab:blue', linewidth=1.8, label='Original Spectrum')
    plt.plot(wl_np, fit_result['g1'], color='tab:green', linewidth=1.4, alpha=0.9, label='Gaussian Peak 1')
    plt.plot(wl_np, fit_result['g2'], color='tab:red', linewidth=1.4, alpha=0.9, label='Gaussian Peak 2')
    plt.plot(wl_np, fit_result['g_sum'], color='tab:orange', linewidth=1.9, linestyle='--', label='Gaussian Sum')

    peak_mu = fit_result['mu']
    peak_amp = fit_result['amps']
    plt.scatter(peak_mu, peak_amp, color='black', s=30, zorder=6, label='Fitted Peak Tops')

    plt.xlabel('Wavelength (nm)', fontsize=15, fontweight='semibold')
    plt.ylabel('Relative Intensity', fontsize=15, fontweight='semibold')
    plt.title('Two-Peak Gaussian Fitting', fontsize=15, fontweight='semibold')
    for spine in plt.gca().spines.values():
        spine.set_linewidth(1.8)
    for label in plt.gca().get_xticklabels():
        label.set_fontweight('semibold')
    for label in plt.gca().get_yticklabels():
        label.set_fontweight('semibold')

    plt.grid(alpha=0.3)
    plt.legend(loc='upper right', prop={'weight': 'semibold', 'size': 11}, frameon=False)
    plt.tight_layout()
    plt.show()



###论文复现部分
def pseudo_voigt(x, x0, gamma, beta):
    gaussian_part = np.exp(-4 * np.log(2) * ((x - x0) / gamma) ** 2)
    lorentz_part = gamma ** 2 / (4 * (x - x0) ** 2 + gamma ** 2)
    return beta * gaussian_part + (1 - beta) * lorentz_part


def multi_peak_model(x, params, n_peaks):
    y = np.zeros_like(x)

    for i in range(n_peaks):
        I = params[i*4 + 0]
        x0 = params[i*4 + 1]
        gamma = params[i*4 + 2]
        beta = params[i*4 + 3]
        

        y += I * pseudo_voigt(x, x0, gamma, beta)


    return y 


def residuals(params, x, y, n_peaks):
    return y - multi_peak_model(x, params, n_peaks)

def init_params(peaks, fwhm, intensity, wl):
    params = []

    Ib = np.min(intensity)

    for i, p in enumerate(peaks):
        I0 = intensity[p] - Ib
        x0 = wl[p]
        gamma = fwhm[i]
        beta = 0.5   # 初始混合

        params.extend([I0, x0, gamma, beta])

    params.append(Ib)

    return np.array(params)



def get_individual_peaks(x, params, n_peaks):
    peaks = []

    for i in range(n_peaks):
        I = params[i*4 + 0]
        x0 = params[i*4 + 1]
        gamma = params[i*4 + 2]
        beta = params[i*4 + 3]

        y = I * pseudo_voigt(x, x0, gamma, beta)
        peaks.append(y)

    Ib = params[-1]

    return np.array(peaks), Ib


def plot_full_result(wl, intensity, result_params, n_peaks):
    # 总拟合
    fitted = multi_peak_model(wl, result_params, n_peaks)

    # 单峰
    peaks, Ib = get_individual_peaks(wl, result_params, n_peaks)

    plt.figure(figsize=(10,6))

    # 原始谱
    plt.plot(wl, intensity, label='Measured Spectrum', linewidth=2)

    # 总拟合
    plt.plot(wl, fitted, '--', label='Fitted Curve', linewidth=2)

    # 单峰
    for i in range(n_peaks):
        plt.plot(wl, peaks[i], linestyle=':', label=f'Peak {i+1}')

    # 背景线
    plt.axhline(Ib, linestyle='--', label='Background')

    plt.xlabel('Wavelength (nm)')
    plt.ylabel('Intensity')
    plt.legend()
    plt.title('LIBS Peak Fitting Result')

    plt.tight_layout()
    plt.show()
        


if __name__ == '__main__':

    peaks, fwhm, cwt_data = cwt_peak_detection(wl, rel_int, scale=0.48, threshold=0.01)
    print(peaks, fwhm)
    plot_result(wl, rel_int, extrema_idx, cwt_data)

    fit_result = fit_two_fixed_gaussian_peaks(wl, rel_int, extrema_idx, cwt_data)
    if fit_result is None:
        print('可用峰数少于2，无法进行双高斯拟合。')
    else:
        print('Two-Gaussian fitting status:', fit_result['success'], fit_result['message'])
        print('mu (fixed):', fit_result['mu'])
        print('sigma (fixed = FWHM/2.355):', fit_result['sigma'])
        print('optimized amplitudes:', fit_result['amps'])
        plot_two_gaussian_fit(wl, rel_int, fit_result)

    # params0 = init_params(peaks, fwhm, rel_int, wl)
    # result = least_squares(
    #     residuals,
    #     params0,
    #     args=(wl, rel_int, len(peaks)),
    #     method='trf'   # Trust Region
    # )
    # fitted = multi_peak_model(wl, result.x, len(peaks))
    
    # plot_full_result(wl, rel_int, result.x, len(peaks))
    
