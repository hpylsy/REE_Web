import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
import scipy.signal as signal
import pywt


#数据导入部分
signal_path=r'D:\LIBS\RREdetectation\MultiPeakfit\4_24data.csv'
data=pd.read_csv(signal_path,header=0,encoding="gbk")

wl=data.iloc[:,0]
rel_int=data.iloc[:,1]
wl=pd.to_numeric(wl, errors='coerce')
rel_int=pd.to_numeric(rel_int, errors='coerce')

valid_mask=wl.notna() & rel_int.notna()
wl=wl[valid_mask]
rel_int=rel_int[valid_mask]
rel_int = rel_int - rel_int.min()





#连续小波（文章复现）
class CWTPeakFWHMEstimator:
    def __init__(self, wl, intensity, scale=10.0, threshold=0.01):

        self.wl = np.asarray(wl, dtype=float)
        self.intensity = np.asarray(intensity, dtype=float)
        self.scale = scale
        self.threshold = threshold
    
    #小波母函数
    def mexican_hat_wavelet(self,points,a):

        A = 2 / (np.sqrt(3 * a) * (np.pi**0.25))
        wsq = a**2
        x = np.linspace(-points//2, points//2, points)
        return A * (1 - x**2/wsq) * np.exp(-x**2/(2*wsq))

    #小波近似二阶导
    def cwt_second_derivative(self):

        scale_val = self.scale

        n = len(self.intensity)
        points = min(200, n)
        if points < 3:
            points = 3
        if points % 2 == 0:
            points -= 1

        wavelet = self.mexican_hat_wavelet(points=points, a=scale_val)
        cwt = np.convolve(self.intensity, wavelet, mode='same')
        return cwt

    def find_peaks_from_second_derivative(self,cwt_data, threshold=0.01):

        minima = signal.argrelextrema(cwt_data, np.less)[0]

        min_val = np.min(cwt_data)
        selected = [i for i in minima if abs(cwt_data[i]) > threshold * abs(min_val)]
        #print (f"找到 {len(selected)} 个满足阈值条件的极小值点，原始极小值点数量: {len(minima)}")
        return np.array(selected, dtype=int)

    def remove_edge_artifacts(self,cwt_data, minima_indices):

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
        return np.array(valid_minima, dtype=int)

    def estimate_fwhm(self, cwt_data, peak_indices, wavelength):
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
    
    
    def cwt_peak_detection(self):
        cwt_data = self.cwt_second_derivative()
        peaks = self.find_peaks_from_second_derivative(cwt_data, self.threshold)

        #去除伪影峰
        peaks = self.remove_edge_artifacts(cwt_data, peaks)
        peaks = np.asarray(peaks, dtype=int)
        fwhm = self.estimate_fwhm(cwt_data, peaks, self.wl)
        return peaks, fwhm, cwt_data

class GaussMultiPeakFitter:
    def __init__(
        self,
        wl,
        rel_int,
        extrema_idx,
        fwhm_selected,
        wl_np,
        selected_idx,
        peak_mu=None,
        peak_height_upper=None,
        fit_left_mu=None,
        fit_right_mu=None,
    ):
        self.wl = np.asarray(wl, dtype=float)
        self.rel_int = np.asarray(rel_int, dtype=float)
        #这里如果做了寻峰,extreme_idx为寻峰结果,但是如果是手动填入,extreme_idx为手动峰位对应的索引
        self.extrema_idx = np.asarray(extrema_idx, dtype=int)
        self.fwhm_selected = np.asarray(fwhm_selected, dtype=float)
        self.wl_np = np.asarray(wl_np, dtype=float)
        self.selected_idx = np.asarray(selected_idx, dtype=int)
        self.peak_mu = None if peak_mu is None else np.asarray(peak_mu, dtype=float)
        self.peak_height_upper = None if peak_height_upper is None else np.asarray(peak_height_upper, dtype=float)
        self.fit_left_mu = None if fit_left_mu is None else float(fit_left_mu)
        self.fit_right_mu = None if fit_right_mu is None else float(fit_right_mu)
        self.fitted_params = []
        self.component_fits = []
        self.total_fit = np.zeros_like(self.wl, dtype=float)
        self.fitted_mu = np.array([])
        self.fitted_amp = np.array([])
        
        #残差分析和迭代拟合结果
        self.residual = np.array([])
        self.residual_linear_fit = np.array([])
        self.new_residual = np.array([])
        self.residual_corrected_components = np.empty((0, self.wl.size), dtype=float)
        self.residual_corrected_total = np.zeros_like(self.wl, dtype=float)
        self.refitted_params = np.empty((0, 3), dtype=float)
        self.refitted_components = np.empty((0, self.wl.size), dtype=float)
        self.refitted_total_fit = np.zeros_like(self.wl, dtype=float)
        self.refit_history = []

    @staticmethod
    def gaussian(x, a, mu, sigma):
        return a * np.exp(-((x - mu) ** 2) / (2 * sigma ** 2))

    def gaussian_sum_fixed_mu(self, x, amps, sigmas, mus):
        y_sum = np.zeros_like(x, dtype=float)
        for a_i, mu_i, sigma_i in zip(amps, mus, sigmas):
            y_sum += self.gaussian(x, a_i, mu_i, sigma_i)
        return y_sum

    def fit(self):
        self.fitted_params = []
        self.component_fits = []
        self.total_fit = np.zeros_like(self.wl, dtype=float)
        self.residual = np.array([])
        self.residual_linear_fit = np.array([])
        self.new_residual = np.array([])
        self.residual_corrected_components = np.empty((0, self.wl.size), dtype=float)
        self.residual_corrected_total = np.zeros_like(self.wl, dtype=float)
        self.refitted_params = np.empty((0, 3), dtype=float)
        self.refitted_components = np.empty((0, self.wl.size), dtype=float)
        self.refitted_total_fit = np.zeros_like(self.wl, dtype=float)
        self.refit_history = []

        x_full = self.wl
        y_full = self.rel_int
        if self.peak_mu is not None:
            peak_mu = self.peak_mu
            if self.peak_height_upper is not None and self.peak_height_upper.size == peak_mu.size:
                peak_height_upper = self.peak_height_upper
            else:
                order = np.argsort(x_full)
                peak_height_upper = np.interp(peak_mu, x_full[order], y_full[order])

            valid_peak_mask = np.isfinite(peak_mu) & np.isfinite(peak_height_upper)
            peak_mu = peak_mu[valid_peak_mask]
            peak_height_upper = peak_height_upper[valid_peak_mask]
        else:
            peak_mu = self.wl[self.extrema_idx]
            peak_height_upper = self.rel_int[self.extrema_idx]

        if peak_mu.size == 0:
            self.fitted_mu = np.array([])
            self.fitted_amp = np.array([])
            return self

        x_span = float(x_full.max() - x_full.min())
        sigma_min = max(x_span / (len(x_full) * 10.0), 1e-4)
        sigma_max = max(x_span / 2.0, sigma_min * 10.0)
        sigma_max = 0.12

        amp_upper = np.maximum(peak_height_upper, 1e-8)
        amp_init = amp_upper * 0.8
        sigma_default = max(x_span / (8.0 * max(peak_mu.size, 1)), sigma_min)

        if self.fwhm_selected.size == peak_mu.size:
            sigma_init = np.clip(self.fwhm_selected / 2.35482, sigma_min, sigma_max)
        else:
            sigma_init = np.full(peak_mu.size, sigma_default, dtype=float)

        x0 = np.concatenate([amp_init, sigma_init])
        bounds = [(0.0, float(u)) for u in amp_upper] + [(sigma_min, sigma_max)] * peak_mu.size

        ratio_candidates = np.arange(0.0, 1.0001, 0.05)
        best_ratio = None
        best_full_rms = np.inf
        best_solution = None
        window_fallback_warned = False

        
        #动态窗口拟合
        for ratio in ratio_candidates:
            # 拟合窗口: 使用最左/最右选中峰作为边界，并按对应 FWHM 动态扩展
            if (
                peak_mu.size >= 1
                and self.fwhm_selected.size == peak_mu.size
                and self.selected_idx.size == peak_mu.size
            ):
                peak_order = np.argsort(self.wl_np[self.selected_idx])
                ordered_idx = self.selected_idx[peak_order]
                ordered_fwhm = self.fwhm_selected[peak_order]
                auto_left_mu = float(self.wl_np[ordered_idx[0]])
                auto_right_mu = float(self.wl_np[ordered_idx[-1]])
                auto_left_fwhm = float(ordered_fwhm[0])
                auto_right_fwhm = float(ordered_fwhm[-1])

                left_mu = auto_left_mu if self.fit_left_mu is None else self.fit_left_mu
                right_mu = auto_right_mu if self.fit_right_mu is None else self.fit_right_mu

                if self.fit_left_mu is None:
                    left_fwhm = auto_left_fwhm
                else:
                    left_fwhm_idx = int(np.argmin(np.abs(peak_mu - left_mu)))
                    left_fwhm = float(self.fwhm_selected[left_fwhm_idx])

                if self.fit_right_mu is None:
                    right_fwhm = auto_right_fwhm
                else:
                    right_fwhm_idx = int(np.argmin(np.abs(peak_mu - right_mu)))
                    right_fwhm = float(self.fwhm_selected[right_fwhm_idx])

                if left_mu > right_mu:
                    left_mu, right_mu = right_mu, left_mu
                    left_fwhm, right_fwhm = right_fwhm, left_fwhm

                fit_mask = (x_full >= left_mu - ratio * left_fwhm) & (x_full <= right_mu + ratio * right_fwhm)
                if np.count_nonzero(fit_mask) < 3:
                    fit_mask = np.ones_like(x_full, dtype=bool)
            else:
                fit_mask = np.ones_like(x_full, dtype=bool)
                if not window_fallback_warned:
                    print('Warning：无法根据 FWHM 和 selected_idx 设置拟合窗口，使用全谱数据进行拟合。')
                    window_fallback_warned = True

            x_fit = x_full[fit_mask]
            y_fit = y_full[fit_mask]

            def window_gaussian_rms(params):
                n_peak = peak_mu.size
                amps = params[:n_peak]
                sigmas = params[n_peak:]
                y_fit_all = self.gaussian_sum_fixed_mu(x_fit, amps, sigmas, peak_mu)
                return float(np.sqrt(np.mean((y_fit - y_fit_all) ** 2)))

            ratio_result = minimize(
                window_gaussian_rms,
                x0=x0,
                method='L-BFGS-B',
                bounds=bounds,
                options={'maxiter': 20000, 'ftol': 1e-12},
            )

            if not ratio_result.success:
                continue

            n_peak = peak_mu.size
            amps_full = ratio_result.x[:n_peak]
            sigmas_full = ratio_result.x[n_peak:]
            y_pred_full = self.gaussian_sum_fixed_mu(x_full, amps_full, sigmas_full, peak_mu)
            full_rms = float(np.sqrt(np.mean((y_full - y_pred_full) ** 2)))

            if full_rms < best_full_rms:
                best_full_rms = full_rms
                best_ratio = float(ratio)
                best_solution = ratio_result.x.copy()

        if best_solution is not None:
            n_peak = peak_mu.size
            best_amps = best_solution[:n_peak]
            best_sigmas = best_solution[n_peak:]

            for a_i, mu_i, sigma_i in zip(best_amps, peak_mu, best_sigmas):
                self.fitted_params.append((float(a_i), float(mu_i), float(sigma_i)))
                y_comp = self.gaussian(x_full, float(a_i), float(mu_i), float(sigma_i))
                self.component_fits.append(y_comp)
                self.total_fit += y_comp

            print(f'Best ratio: {best_ratio:.2f}, Full-spectrum RMS: {best_full_rms:.6f}')

        else:
            print('Global gaussian fitting failed for all ratio candidates.')
        iterative_switch = False
        if self.fitted_params and iterative_switch:
            fitted_params_arr = np.array(self.fitted_params, dtype=float)
            self.fitted_mu = fitted_params_arr[:, 1]
            self.fitted_amp = fitted_params_arr[:, 0]
            print('Fitted peaks (A, mu, sigma):')
            print(pd.DataFrame(fitted_params_arr, columns=['A', 'mu', 'sigma']))

            current_params = fitted_params_arr.copy()
            self.refit_history = []
            refit_iterations = 10

            for iter_idx in range(refit_iterations):
                (
                    self.residual,
                    self.residual_linear_fit,
                    self.new_residual,
                    self.residual_corrected_components,
                    self.residual_corrected_total,
                    self.refitted_params,
                    self.refitted_components,
                    self.refitted_total_fit,
                ) = self.residual_iterative_fit(current_params, x_full, y_full)

                refit_rms = float(np.sqrt(np.mean((y_full - self.refitted_total_fit) ** 2)))
                self.refit_history.append({
                    'iteration': iter_idx + 1,
                    'params': self.refitted_params.copy(),
                    'components': self.refitted_components.copy(),
                    'total_fit': self.refitted_total_fit.copy(),
                    'rms': refit_rms,
                })

                if self.refitted_params.size == 0:
                    break

                current_params = self.refitted_params.copy()

            print(f'Refitted corrected peaks with fixed mu after {len(self.refit_history)} iterations (A, mu, sigma):')
            print(pd.DataFrame(self.refitted_params, columns=['A', 'mu', 'sigma']))
        else:
            self.fitted_mu = np.array([])
            self.fitted_amp = np.array([])
            self.residual = np.array([])
            self.residual_linear_fit = np.array([])
            self.new_residual = np.array([])
            self.residual_corrected_components = np.empty((0, self.wl.size), dtype=float)
            self.residual_corrected_total = np.zeros_like(self.wl, dtype=float)
            self.refitted_params = np.empty((0, 3), dtype=float)
            self.refitted_components = np.empty((0, self.wl.size), dtype=float)
            self.refitted_total_fit = np.zeros_like(self.wl, dtype=float)
            self.refit_history = []

        return self

    @staticmethod
    def residual_iterative_fit(fitted_params, x_full, y_full):
        x_arr = np.asarray(x_full, dtype=float)
        y_arr = np.asarray(y_full, dtype=float)
        component_fits = []
        total_fit = np.zeros_like(y_arr, dtype=float)

        for a_i, mu_i, sigma_i in fitted_params:
            y_comp = GaussMultiPeakFitter.gaussian(x_arr, float(a_i), float(mu_i), float(sigma_i))
            component_fits.append(y_comp)
            total_fit += y_comp

        residual = y_arr - total_fit

        valid_mask = np.isfinite(x_arr) & np.isfinite(residual)
        if np.count_nonzero(valid_mask) < 2:
            raise ValueError('At least two valid points are required for residual linear regression.')

        slope, intercept = np.polyfit(x_arr[valid_mask], residual[valid_mask], 1)
        residual_linear_fit = slope * x_arr + intercept
        new_residual = residual - residual_linear_fit

        
        #零检验
        if len(component_fits) == 0:
            residual_corrected_components = np.empty((0, y_arr.size), dtype=float)
            residual_corrected_total = np.zeros_like(y_arr, dtype=float)
            refitted_params = np.empty((0, 3), dtype=float)
            refitted_components = np.empty((0, y_arr.size), dtype=float)
            refitted_total = np.zeros_like(y_arr, dtype=float)
            return (
                residual,
                residual_linear_fit,
                new_residual,
                residual_corrected_components,
                residual_corrected_total,
                refitted_params,
                refitted_components,
                refitted_total,
            )

        
        #残差比例处理
        component_fits = np.asarray(component_fits, dtype=float)
        component_sum = np.sum(component_fits, axis=0)
        component_weights = np.divide(
            component_fits,
            component_sum,
            out=np.zeros_like(component_fits),
            where=np.abs(component_sum) > 1e-12,
        )
        
        residual_corrected_components = component_fits + component_weights * residual
        residual_corrected_total = np.sum(residual_corrected_components, axis=0)

        x_span = float(np.nanmax(x_arr) - np.nanmin(x_arr))
        sigma_min = max(x_span / (len(x_arr) * 10.0), 1e-4)
        sigma_max = max(x_span / 2.0, sigma_min * 10.0)
        refitted_params = []
        refitted_components = []

        for y_target, (a_i, mu_i, sigma_i) in zip(residual_corrected_components, fitted_params):
            y_target = np.asarray(y_target, dtype=float)
            valid_component_mask = np.isfinite(x_arr) & np.isfinite(y_target)

            if np.count_nonzero(valid_component_mask) < 2:
                refit_a = float(a_i)
                refit_sigma = float(np.clip(sigma_i, sigma_min, sigma_max))
            else:
                peak_idx = int(np.argmin(np.abs(x_arr - float(mu_i))))
                amp_at_center = max(float(y_target[peak_idx]), 1e-8)
                #修正峰取值上限，防止过拟合
                amp_upper = max(
                    float(np.nanmax(y_target[valid_component_mask])),
                    float(a_i),
                    amp_at_center,
                    1e-8,
                )
                amp_init = min(max(float(a_i), amp_at_center), amp_upper)
                sigma_init = float(np.clip(sigma_i, sigma_min, sigma_max))

                def fixed_mu_gaussian_rms(params):
                    amp, sigma = params
                    y_pred = GaussMultiPeakFitter.gaussian(
                        x_arr[valid_component_mask],
                        amp,
                        float(mu_i),
                        sigma,
                    )
                    return float(np.sqrt(np.mean((y_target[valid_component_mask] - y_pred) ** 2)))

                refit_result = minimize(
                    fixed_mu_gaussian_rms,
                    x0=np.array([amp_init, sigma_init], dtype=float),
                    method='L-BFGS-B',
                    bounds=[(0.0, amp_upper), (sigma_min, sigma_max)],
                    options={'maxiter': 20000, 'ftol': 1e-12},
                )

                if refit_result.success:
                    refit_a = float(refit_result.x[0])
                    refit_sigma = float(refit_result.x[1])
                else:
                    refit_a = float(a_i)
                    refit_sigma = sigma_init

            refitted_params.append((refit_a, float(mu_i), refit_sigma))
            refitted_components.append(
                GaussMultiPeakFitter.gaussian(x_arr, refit_a, float(mu_i), refit_sigma)
            )

        refitted_params = np.asarray(refitted_params, dtype=float)
        refitted_components = np.asarray(refitted_components, dtype=float)
        refitted_total = np.sum(refitted_components, axis=0)

        return (
            residual,
            residual_linear_fit,
            new_residual,
            residual_corrected_components,
            residual_corrected_total,
            refitted_params,
            refitted_components,
            refitted_total,
        )

        
    
    def plot(self, peak_wl, peak_int):
        plt.figure(figsize=(7,5))
        plt.plot(self.wl, self.rel_int, color='tab:blue', linewidth=1.8, label='wl-int')

        if self.component_fits:
            for idx, y_comp in enumerate(self.component_fits):
                if idx == 0:
                    plt.plot(self.wl, y_comp, color='tab:green', linewidth=1.2, alpha=0.85, label='Gaussian Components')
                else:
                    plt.plot(self.wl, y_comp, color='tab:green', linewidth=1.2, alpha=0.85)

        if self.fitted_params:
            plt.plot(self.wl, self.total_fit, color='tab:orange', linewidth=1.8, linestyle='--', label='Gaussian Sum Fit')
            plt.scatter(self.fitted_mu, self.fitted_amp, color='tab:green', s=28, label='Fitted Peaks', zorder=6)

        plt.xlabel('Wavelength (nm)', fontsize=15, fontweight="semibold")
        plt.ylabel('Relative Intensity', fontsize=15, fontweight="semibold")
        plt.title('Wavelength-Intensity Spectrum', fontsize=15, fontweight="semibold")
        for spine in plt.gca().spines.values():
            spine.set_linewidth(1.8)
        for label in plt.gca().get_xticklabels():
            label.set_fontweight("semibold")
        for label in plt.gca().get_yticklabels():
            label.set_fontweight("semibold")
        plt.scatter(peak_wl, peak_int, color='tab:red', s=36, label='Local Extrema', zorder=5)

        plt.grid(alpha=0.3)
        plt.legend(loc='upper right', prop={"weight": "semibold", "size": 12}, frameon=False)
        plt.tight_layout()
        plt.show()

if __name__ == '__main__':
    # 自动找局部极大值  
    extrema_idx = []
    for i in range(1, len(rel_int) - 1):
        is_local_max = rel_int.iloc[i] > rel_int.iloc[i - 1] and rel_int.iloc[i] > rel_int.iloc[i + 1]
        if is_local_max:
            extrema_idx.append(i)

    manual_peak_wl = [
        #  275.43, 275.57,275.70

        305.85,306.20
    ]

    if len(manual_peak_wl) > 0:
        wl_np_for_peak = wl.to_numpy(dtype=float)
        int_np_for_peak = rel_int.to_numpy(dtype=float)
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
            print(f"跳过超出截取窗口、无法插值的手动峰位: {skipped_peak_wl.tolist()}")

        #插值部分
        manual_peak_wl_np = np.sort(manual_peak_wl_np[in_range_mask])
        peak_wl = pd.Series(manual_peak_wl_np)
        peak_int = pd.Series(np.interp(manual_peak_wl_np, wl_sorted_for_peak, int_sorted_for_peak))

        # FWHM 估计仍基于离散 CWT 结果，这里只保留最近采样点索引用于估计峰宽。
        extrema_idx = sorted(int(np.argmin(np.abs(wl_np_for_peak - target_mu))) for target_mu in manual_peak_wl_np)

    if len(extrema_idx) == 0:
        raise ValueError('未找到可用峰位，请检查数据或 manual_peak_wl 设置。')

    if len(manual_peak_wl) == 0:
        peak_wl = wl.iloc[extrema_idx]
        peak_int = rel_int.iloc[extrema_idx]


    #估计所有选中峰的FWHM
    estimator = CWTPeakFWHMEstimator(wl, rel_int, scale=0.48, threshold=0.01)
    cwt_peaks, cwt_fwhm, cwt_data = estimator.cwt_peak_detection()

    wl_np = np.asarray(wl, dtype=float)
    peak_indices = np.asarray(extrema_idx, dtype=int)
    peak_indices = peak_indices[(peak_indices >= 0) & (peak_indices < len(wl_np))]

    selected_idx = np.sort(peak_indices)
    fwhm_selected = estimator.estimate_fwhm(np.asarray(cwt_data, dtype=float), selected_idx, wl_np)
    print(f"Estimated FWHM for selected peaks: {fwhm_selected}")

    fitter = GaussMultiPeakFitter(
        wl=wl,
        rel_int=rel_int,
        extrema_idx=extrema_idx,
        fwhm_selected=fwhm_selected,
        wl_np=wl_np,
        selected_idx=selected_idx,
        peak_mu=peak_wl.to_numpy(dtype=float),
        peak_height_upper=peak_int.to_numpy(dtype=float),
    )
    fitter.fit()
    fitter.plot(peak_wl=peak_wl.to_numpy(dtype=float), peak_int=peak_int.to_numpy(dtype=float))
    
    # print(fitter.wl)
    # print(fitter.rel_int)
    # print(fitter.fitted_params)
    # print(fitter.total_fit)










