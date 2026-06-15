import sys
import math
import time
import os
import matplotlib
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
from PyQt5.QtWidgets import QMainWindow, QApplication, QGridLayout, QFileDialog
# matplotlib.use("Qt5Agg")  # 声明使用QT5
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from scipy.signal import savgol_filter, find_peaks
from newui import Ui_MainWindow
from sklearn.metrics import mean_squared_error
import warnings
from lmfit.models import LorentzianModel, VoigtModel

class myfunction():
    def find_nearest(array, value):
        c = []  # 最近值列表
        c_index = []  # 最近值索引列表
        peak_indices = []  # 最近峰值位置索引列表

        # 找到数组中的所有峰值位置
        peaks, _ = find_peaks(array)
        used_peaks = set()  # 用于跟踪已使用的峰值索引，避免重叠

        for i in range(len(value)):

            idx = np.searchsorted(array, value[i], side="left")


            if idx > 0 and (idx == len(array) or abs(value[i] - array[idx - 1]) < abs(value[i] - array[idx])):
                nearest_index = idx - 1
            else:
                nearest_index = idx

            # 添加最近值及其索引
            c.append(array[nearest_index])
            c_index.append(nearest_index)

            # 找到最接近的峰值索引，且不与之前的峰值重叠
            if len(peaks) > 0:
                peak_diffs = np.abs(array[peaks] - value[i])  # 计算每个峰值与当前值之间的距离
                sorted_peak_indices = np.argsort(peak_diffs)  # 按距离从小到大排序峰值索引

                # 找到最近的未使用的峰值
                nearest_peak_idx = None
                for peak_idx in sorted_peak_indices:
                    if peaks[peak_idx] not in used_peaks:
                        nearest_peak_idx = peaks[peak_idx]
                        used_peaks.add(nearest_peak_idx)
                        break

                peak_indices.append(nearest_peak_idx)
            else:
                peak_indices.append(None)  # 如果没有峰值，返回 None

        return c, c_index

    def rough2acc(dotindex_rough, average_spectrum):
        dotindex_acc = []
        for id in range(len(dotindex_rough)):
            avsp = average_spectrum.tolist()
            new_id = dotindex_rough[id]
            while avsp[new_id] < max(avsp[new_id - 1], avsp[new_id + 1]):
                dot_left = avsp[new_id - 1]
                dot_right = avsp[new_id + 1]
                if dot_right < dot_left:
                    new_id = new_id - 1
                else:
                    new_id = new_id + 1
            dotindex_acc.append(new_id)
        return dotindex_acc

    def excel2array(path, sheet, delect1, delect2):
        df = pd.read_excel(path, sheet_name=sheet)
        data = df.iloc[(delect1 - 1):-delect2].values
        return data

    def csv2array(path, delect1, delect2):
        df = pd.read_csv(path, encoding='gbk')
        data = df.iloc[(delect1 - 1):-delect2].values
        return data

    def getparameter(origin_select_wave, col_name, col):
        a = origin_select_wave[:, col_name.index(col)].tolist()
        a.remove(col)
        return a

    def linear_regression(x, y):
        N = len(x)
        if N <= 1:
            X1, Y1, a11, a10, R2 =x, y, 1, 0, 1
        else:
            sumx = sum(x)
            sumy = sum(y)
            sumx2 = sum(x ** 2)
            sumxy = sum(x * y)

            A = np.asmatrix([[N, sumx], [sumx, sumx2]])
            b = np.array([sumy, sumxy])
            a10, a11 = np.linalg.solve(A, b)

            X1 = np.arange(min(x), max(x), 0.001)
            Y1 = np.array([a10 + a11 * x_i for x_i in X1])
            y_fitting = np.array([a10 + a11 * x_ii for x_ii in x])
            y_mean = sum(y) / len(y)
            s_list1 = [(y_i - y_mean) ** 2 for y_i in y]
            sst = sum(s_list1)
            s_list2 = [(y_ii - y_mean) ** 2 for y_ii in y_fitting]
            ssr = sum(s_list2)
            R2 = ssr / sst
        return X1, Y1, a11, a10, R2

    def check_au(x, y, check):
        x, y = x.tolist(), y.tolist()
        bochang = check[:, 0].tolist()
        xiaolu = check[:, 1].tolist()
        if len(y) == len(xiaolu):
            wave = np.zeros(len(y))
            au = np.zeros(len(y))
            for i in range(len(y)):
                au[i] = y[i] / xiaolu[i]
                wave[i] = x[i]
        elif bochang[0] - x[0] > 0.0001:
            start = x.index(min(x, key=lambda x1: abs(x1 - bochang[0])))
            if len(y) - start < len(xiaolu):
                l = len(y) - start
            else:
                l = len(xiaolu)
            wave, au = np.zeros(l), np.zeros(l)
            for i in range(l):
                au[i] = y[start + i] / xiaolu[i]
                wave[i] = x[start + i]
        elif x[0] - bochang[0] > 0.0001:
            x[0] = min(bochang, key=lambda x1: abs(x1 - x[0]))
            start = bochang.index(x[0])
            if len(xiaolu) - start < len(y):
                l = len(xiaolu) - start
            else:
                l = len(y)
            wave, au = np.zeros(l), np.zeros(l)
            for i in range(l):
                au[i] = y[i] / xiaolu[start + i]
                wave[i] = x[i]

        return wave, au
    @staticmethod
    def background_remove(intensity_data, r=0.0001, max_iter=1000):
        """
        去除光谱背景
        
        参数:
        intensity_data: 输入强度数据，一维numpy数组或列表
        r: 收敛阈值，默认0.0001
        max_iter: 最大迭代次数，默认1000
        
        返回:
        去背景后的强度数据，一维numpy数组
        """
        
        # 确保输入是numpy数组
        if not isinstance(intensity_data, np.ndarray):
            intensity_data = np.array(intensity_data)
            
        I = intensity_data.copy()
        
        def remove_background_internal(I, r, max_iter):
            Value = I.copy()
            row_count = len(Value)
            iter_initial = 0

            while (iter_initial < max_iter):
                # 一阶剥峰
                empty_array = np.empty_like(Value)

                # 边缘值处理
                empty_array[0] = Value[0] / 2 
                empty_array[row_count-1] = Value[row_count-1] / 2

                for i in range(1, row_count-1):
                    empty_array[i] = min(Value[i], (Value[i-1] + Value[i+1]) / 2)

                difference = abs(Value - empty_array)
                differ = np.sum(difference)
                
                if (differ / np.sum(Value)) < r:
                    Value = empty_array
                    break
                Value = empty_array

                # 六阶剥峰   
                empty_array = np.empty_like(Value)

                empty_array[0:5] = Value[0:5] / 2
                empty_array[row_count-5:row_count] = Value[row_count-5:row_count] / 2

                for i in range(6, row_count-6):
                    empty_array[i] = min(Value[i], (Value[i-6] + Value[i+6]) / 2)
                    
                difference = abs(Value - empty_array)
                differ = np.sum(difference)

                if (differ / np.sum(Value)) < r:
                    Value = empty_array
                    break
                Value = empty_array
                iter_initial += 1

            return Value, iter_initial
        
        # 调用内部函数获取背景
        Background, iter_count = remove_background_internal(I, r, max_iter)
        
        # 计算去背景后的强度
        I_corrected = I - Background
        
        return I_corrected


    def R2(n, y, yy):
        if n == 1:
            R2 = 1.0
        else:
            R2 = np.corrcoef(y, yy)[0, 1]
            R2 = R2 ** 2
            if round(R2, 3) == 1:
                R2 = 0.999
        return R2

    @staticmethod
    def Electron_density (wavelengths, intensities):
        def lorentzian_fit_and_plot(wavelengths, intensities):
            mask = (wavelengths >= 654.5) & (wavelengths < 658.5)
            filtered_wavelength = wavelengths[mask]
            filtered_intensity = intensities[mask]

            model = LorentzianModel()
            params = model.guess(filtered_intensity, x=filtered_wavelength)
            result = model.fit(filtered_intensity, params, x=filtered_wavelength)
            fwhm = result.params['fwhm'].value
            return fwhm

        lorentz_fwhm = lorentzian_fit_and_plot(wavelengths, intensities)
        #lorentz_fwhm = 2
        Ne = 8.02e12 * (lorentz_fwhm / 0.00186) ** (3/2)
        print(f"Ne = {Ne:.2e} cm^-3")
        #Ne = 5e23
        return Ne

class CFLIBS():
    def __init__(self):
        self.kB = (1.380649 * (10 ** (-23)))* (6.24 * (10 ** 18))
        self.me = 9.10938 * (10 ** (-31))
        self.h = 6.62607015 * (10 ** (-34))
        self.T0 = 10000
        #self.Ne_cm = myfunction.Electron_density(test_2, test_1)
        #self.Ne = self.Ne_cm * 1e6 #转换成m^-3
        self.Ne = 4.7e23

        self.lastx = 0
        self.lasty = 0
        self.press = False
        self.main()

    def main(self):
        t0 = time.time()
        self.color = ['blue', 'green', 'red', 'purple', 'cyan', 'black', 'orange', 'pink', 'yellow', 'gray', 'brown']
        self.specie_name = load_1
        self.check_data = load_5
        self.atomicmass, self.Eion, self.UT = load_8, load_9, load_10
        self.specie_sheet = load_11
        for o in range(1, len(self.Eion[1])):
            self.Eion[1][o] = np.float64(self.Eion[1][o])
        self.average_spectrum_test, self.wavelength_test = test_1, test_2
        self.T_total_uno = self.calculate_temperature(element_massage, 'uno')

        cflibsan, ueq_all, UT_all = [], [], []

        for j in range(len(self.specie_name)):
            specie = self.specie_name[j]
            self.color = color[j]
            Eion = np.float64(self.Eion[1][self.Eion[0].index(specie)])
            ueq, an, UT = self.bolztman_plot(specie, self.T_total_uno, element_massage[j], Eion, 'uno')
            cflibsan.append(an)
            UT_all.append(UT)
            ueq_all.append(ueq)

        self.caluno_an(ueq_all, UT_all)
        #self.unnomalization(ueq_all)

        plt.show()

    def calculate_ut(self, specie, T):
        data = self.UT
        beta = 1 / (self.kB * T)
        specie1, specie2 = specie + ' I', specie + ' II'
        species_name = data[0, :]
        index1, index2 = species_name.tolist().index(specie1), species_name.tolist().index(specie2)
        w1, w2 = data[:, index1 + 1], data[:, index2 + 1]
        e1, e2 = data[:, index1 + 2], data[:, index2 + 2]
        w1, w2 = [x for x in w1 if not math.isnan(x)], [x for x in w2 if not math.isnan(x)]
        e1, e2 = [x for x in e1 if not math.isnan(x)], [x for x in e2 if not math.isnan(x)]
        z1, z2 = np.zeros(len(w1)), np.zeros(len(w2))
        for i in range(len(w1)):
            z1[i] = w1[i] * np.exp(-beta * e1[i])
        for j in range(len(w2)):
            z2[j] = w2[j] * np.exp(-beta * e2[j])
        UT1, UT2 = sum(z1), sum(z2)
        return UT1, UT2

    def get_UTNC(self, specie_name, T):
        UT = self.calculate_ut(specie_name, T)
        atomic_mass = self.atomicmass[1][self.atomicmass[0].index(specie_name)]
        UT, atomic_mass = np.float64(UT), np.float64(atomic_mass)
        return UT,  atomic_mass

    def departion(self, ion, I, A, Ek, gk):
        L = len(ion)
        if 'saha-boltzmann' in ion:
            I_saha, gk_saha, A_saha, Ek_saha = [], [], [], []
            for ion_i in range(L):
                if ion[ion_i] == 'saha-boltzmann':
                    I_saha.append(I[ion_i])
                    gk_saha.append(gk[ion_i])
                    A_saha.append(A[ion_i])
                    Ek_saha.append(Ek[ion_i])
            gk_saha, A_saha, Ek_saha= np.array(gk_saha), np.array(A_saha), np.array(Ek_saha)
        else:
            I_saha = []
            gk_saha, A_saha, Ek_saha = [], [], []

        if 'boltzmann' in ion:
            I_bolz, gk_bolz, A_bolz, Ek_bolz = [], [], [], []
            for ion_i in range(L):
                if ion[ion_i] == 'boltzmann':
                    I_bolz.append(I[ion_i])
                    gk_bolz.append(gk[ion_i])
                    A_bolz.append(A[ion_i])
                    Ek_bolz.append(Ek[ion_i])
            gk_bolz = np.array(gk_bolz)
            A_bolz = np.array(A_bolz)
            Ek_bolz = np.array(Ek_bolz)
        else:
            I_bolz = []
            gk_bolz, A_bolz, Ek_bolz = [], [], []

        return I_bolz, I_saha, [A_bolz, A_saha, gk_bolz, gk_saha, Ek_bolz, Ek_saha]

    def calculate_temperature(self, element_massage, roru):
        T_i, T_total = 0, []
        l = len(self.specie_name)
        for j in range(l):
            specie = self.specie_name[j]
            color = self.color[j]
            parameter, I_test, dotindex_acc_test, ion = element_massage[j]
            I_bolz, I_saha = I_test[0], I_test[1]

            if specie == 'Ti' or specie =='V':
                T_i = T_i + 1
                Eion = np.float64(self.Eion[1][self.Eion[0].index(specie)])
                Ek_bolz, Ek_saha = parameter[4], parameter[5]
                gk_bolz, gk_saha = parameter[2], parameter[3]
                A_bolz, A_saha = parameter[0], parameter[1]

                y_bolz = np.log(I_bolz / (gk_bolz * A_bolz))
                x_bolz = Ek_bolz

                T = self.T0
                Eion = np.float64(Eion) * np.ones(len(Ek_saha))
                while True:
                    beta = self.kB * T / (6.24 * (10 ** 18))
                    y_saha = np.log(I_saha / (gk_saha * A_saha)) - np.log(
                        (2 * ((2 * np.pi * self.me * beta) ** 1.5)) / (self.Ne * self.h ** 3))
                    x_saha = Ek_saha + Eion
                    x = np.hstack((x_bolz, x_saha))
                    y = np.hstack((y_bolz, y_saha))
                    xx, yy, m, q, R2 = myfunction.linear_regression(x, y)
                    T_lass = T
                    T = -1 / (self.kB * m)
                    if abs((T - T_lass) / T_lass) < 0.0001:
                        break
                T_total.append(T)
                if roru == 'uno':
                    ax2.scatter(x, y, s=15, color=color)
                    ax2.plot(xx, yy, color=color, label=f'{specie}, T={round(T / 11605, 2)}eV')
                    ax2.set_xlabel("(eV)", size=10)
                    ax2.set_ylabel("(a.u.)", size=10)
                    ax2.legend(loc='best', fontsize=7)
            else:
                T_total.append(0)

        temperture = sum(T_total) / T_i
        print(f"The plasma temperature is {round(temperture, 3)} K")
        return temperture

    def bolztman_plot(self, specie_name, T, one_element_massage, Eion, type):
        parameter, I_test, dotindex_acc_test, ion = one_element_massage
        I_bolz, I_saha = np.array(I_test[0]), np.array(I_test[1])
        A_bolz, A_saha = np.array(parameter[0]), np.array(parameter[1])
        gk_bolz, gk_saha = np.array(parameter[2]), np.array(parameter[3])
        Ek_bolz, Ek_saha = np.array(parameter[4]), np.array(parameter[5])
        UT, atomic_mass = self.get_UTNC(specie_name, T)
        beta = 1 / (self.kB * T)
        d1 = 2 * UT[1] * np.exp(-Eion * beta)
        d2 = (2 * np.pi * self.me * (self.kB / (6.25 * (10 ** 18))) * T) ** 1.5
        d3 = self.Ne * UT[0] * (self.h ** 3)

        if 'boltzmann' in ion and 'saha-boltzmann' in ion:
            I_bolz_correct, I_saha_correct = I_bolz, I_saha
            x_bolz, x_saha = Ek_bolz, Ek_saha
            y_bolz = np.log(I_bolz_correct / (gk_bolz * A_bolz))
            y_saha = np.log(I_saha_correct / (gk_saha * A_saha))
            q_bolz, q_saha = np.mean(y_bolz) + beta * np.mean(x_bolz), np.mean(y_saha) + beta * np.mean(x_saha)
            xx_bolz, xx_saha = np.linspace(0, 12, 1000), np.linspace(0, 12, 1000)
            yy_bolz, yy_saha = -beta * xx_bolz + q_bolz, -beta * xx_saha + q_saha
            y2_bolz, y2_saha = -beta * x_bolz + q_bolz, -beta * x_saha + q_saha
            R2_bolz = format(myfunction.R2(len(y_bolz), y_bolz, y2_bolz), '.3f')
            R2_saha = format(myfunction.R2(len(y_saha), y_saha, y2_saha), '.3f')

            ueql = np.exp(q_bolz) * UT[0]
            ueqll = np.exp(q_saha) * UT[1]
            ueq = ueqll + ueql

            if type == 'uno':
                ax3.scatter(x_bolz, y_bolz, s=30, c=self.color,
                            marker='o', label=f'{specie_name} I, R2={R2_bolz}')
                ax3.plot(xx_bolz, yy_bolz, '-', c=self.color)
                ax3.scatter(x_saha, y_saha, s=30, c=self.color,
                            marker='x', label=f'{specie_name} II, R2={R2_saha}')
                ax3.plot(xx_saha, yy_saha, '--', c=self.color)

        elif 'boltzmann' in ion:
            I_bolz_correct = I_bolz
            x_bolz = Ek_bolz
            y_bolz = np.log(I_bolz_correct / (gk_bolz * A_bolz))
            q_bolz = np.mean(y_bolz) + beta * np.mean(x_bolz)
            xx_bolz = np.linspace(0, 12, 1000)
            yy_bolz = -beta * xx_bolz + q_bolz
            y2_bolz = -beta * x_bolz + q_bolz
            R2_bolz = format(myfunction.R2(len(y_bolz), y_bolz, y2_bolz), '.3f')
            ueql = np.exp(q_bolz) * UT[0]
            ueqll = (d1 * d2 * ueql) / d3
            ueq = ueqll + ueql
            if type == 'uno':
                ax3.scatter(x_bolz, y_bolz, s=30, c=self.color, marker='o', label=f'{specie_name} I, R2={R2_bolz}')
                ax3.plot(xx_bolz, yy_bolz, '-', c=self.color)

        elif 'saha-boltzmann' in ion:
            I_saha_correct = I_saha
            x_saha = Ek_saha
            y_saha = np.log(I_saha_correct / (gk_saha * A_saha))
            q_saha = np.mean(y_saha) + beta * np.mean(x_saha)
            xx_saha = np.linspace(0, 12, 1000)
            yy_saha = -beta * xx_saha + q_saha
            y2_saha = -beta * x_saha + q_saha
            R2_saha = format(myfunction.R2(len(y_saha), y_saha, y2_saha), '.3f')
            ueqll = np.exp(q_saha) * UT[1]
            ueql = (d3 * ueqll) / (d1 * d2)
            ueq = ueqll + ueql
            if type == 'uno':
                ax3.scatter(x_saha, y_saha, s=30, c=self.color,
                            marker='x', label=f'{specie_name} II, R2={R2_saha}')
                ax3.plot(xx_saha, yy_saha, '--', c=self.color)

        ax3.set_xlabel("(eV)", size=10)
        ax3.set_ylabel("(a.u.)", size=10)
        if type == 'uno':
            ax3.legend(loc='best', fontsize=7)
        return [ueql, ueqll], ueq, [UT[0], UT[1]]

    def caluno_an(self, ueq_all, UT_all):
        global F_constant, resultcf
        AUeq = []
        for k in range(len(self.specie_name)):
            specie = self.specie_name[k]
            atomic_mass = self.atomicmass[1][list(self.atomicmass[0]).index(specie)]
            aueq = np.float64(atomic_mass) * (ueq_all[k][0] + ueq_all[k][1])
            AUeq.append(aueq)
        F_constant = sum(AUeq)
        #F_constant = F_constant
        resultcf = []
        for z in range(len(self.specie_name)):
            specie = self.specie_name[z]
            atomic_mass = self.atomicmass[1][list(self.atomicmass[0]).index(specie)]
            cs = (np.float64(atomic_mass) * (ueq_all[z][0] + ueq_all[z][1])) / F_constant
            resultcf.append(cs)

        return


class Mywindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        #self.intensity_threshold = 2000
        # self.snr_threshold = 3
        self.test_filename = ""
        self.test_shuju = 0
        self.checkBox.setChecked(True)
        self.pushButton_load_test.clicked.connect(self.test_load_method)
        self.pushButton_start.clicked.connect(self.start_method)
        self.pushButton_quit.clicked.connect(self.exist_method)
        self.setWindowTitle("自由定标法")
        self.spectrum.setTitle(f"Spectrum")
        self.sahaplot.setTitle('Saha-Boltzmann Plot')
        self.cf.setTitle('Boltzmann Plot of CF')
        self.groupBox_4.setTitle('Result')
        self.gridlayout_1 = QGridLayout(self.spectrum)
        self.gridlayoutsaha = QGridLayout(self.sahaplot)
        self.gridlayoutcf = QGridLayout(self.cf)

    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def set_figure(self, item):
        self.fig = plt.figure(figsize=(10, 9), facecolor='#B7B7B7')
        ax = []
        for i in range(item):
            ax0 = self.fig.add_subplot(2, 2, i+1, facecolor='#FFFACD')
            ax0.grid(True)
            ax.append(ax0)
        plt.subplots_adjust(top=0.95, bottom=0.08, left=0.095, right=0.97, hspace=0.265, wspace=0.240)
        return ax[0], ax[1], ax[2]

    def test_load_method(self):
        f_path, _ = QFileDialog.getOpenFileName(self, "选择光谱数据(CSV)", "", "CSV files (*.csv)")
        if f_path:
            self.test_path = f_path
            self.test_filename = os.path.basename(f_path)
            global element_massage, load_1, load_5, load_8, load_9, load_10, load_11, color
            t0t = time.time()
            load_1, load_5, load_8, load_9, load_10, load_11 = self.load_refer_dataset(self.test_path)
            color = ['blue', 'green', 'red', 'purple', 'cyan', 'black', 'orange', 'pink', 'yellow', 'gray', 'brown']
            for o in range(1, len(load_9[1])):
                load_9[1][o] = np.float64(load_9[1][o])
            self.average_spectrum_test, self.wavelength_test = self.load_test_dataset(self.test_path)
            self.test_shuju = 1
            t2 = time.time()
            self.lineEdit.setText(f'文件路径：{f_path}, 本次读取用时{round(t2 - t0t, 3)}s')

            self.clear_layout(self.gridlayout_1)

            self.F1 = MyFigure()
            self.ax1 = self.F1.fig.add_subplot(111)

            self.average_spectrum_test = myfunction.background_remove(self.average_spectrum_test)

            self.efficencychceck('on')

            l = len(self.specie_name)
            self.ax1print = l
            element_massage = []
            for i in range(l):
                specie = self.specie_name[i]
                self.color = color[i]
                parameter, I_test_bolz, I_test_saha, dotindex_acc_test, ion = self.get_IAgEion(specie)
                element_massage.append([parameter, [I_test_bolz, I_test_saha], dotindex_acc_test, ion])

            if self.checkBox.isChecked():
                self.gridlayout_1.addWidget(self.F1)
            self.run = 0
        else:
            self.lineEdit.setText(f'请选择文件')
            self.test_shuju = 0

    def start_method (self):
        if  self.test_shuju == 1:
            t0O = time.time()
            global ax2, ax3
            self.clear_layout(self.gridlayoutsaha)
            self.clear_layout(self.gridlayoutcf)

            self.F2 = OtherFigure()
            ax2 = self.F2.fig2.add_subplot(111)
            self.F3 = OtherFigure()
            ax3 = self.F3.fig2.add_subplot(111)
            CFLIBS()
            self.resultprintout()
            if self.checkBox.isChecked():
                self.gridlayoutsaha.addWidget(self.F2)
                self.gridlayoutcf.addWidget(self.F3)
            t3 = time.time()
            self.lineEdit.setText(f'本次计算用时{round(t3 - t0O, 3)}s')
        else:
            self.lineEdit.setText(f'缺少数据')

    def load_refer_dataset(self, path0):
        path = os.path.dirname(path0)
        self.check_path = path + r'\bin铝合金\myiccdcheck_lvbo.csv'
        self.candm_path = path + r'\bin铝合金\candm.csv'
        self.UT_path = path + r'\bin铝合金\UT.csv'
        self.species_path = path + r'\bin铝合金\species.xlsx'

        specie_name = []
        specie_sheet = []

        check_data = myfunction.csv2array(self.check_path, 1, 1)
        candm = myfunction.csv2array(self.candm_path, 1, 1)

        atomicmass = [candm[0, :].tolist(), candm[2, :].tolist()]
        Eion = [candm[0, :].tolist(), candm[3, :].tolist()]

        UT = myfunction.csv2array(self.UT_path, 1, 1)

        sheet_total = pd.ExcelFile(self.species_path).sheet_names
        for sheet_i in range(len(sheet_total)):
            specie_name.append(sheet_total[sheet_i])
            specie_sheet.append(myfunction.excel2array(self.species_path, sheet_total[sheet_i], 1, 1))
        self.specie_name, self.specie_sheet = specie_name, specie_sheet

        return specie_name, check_data, atomicmass, Eion, UT, specie_sheet

    def load_test_dataset(self, test_path):
        test_data = myfunction.csv2array(test_path, 1, 1)
        wavelength_test = test_data[:, 0]
        measurement_test = test_data.shape[1] - 1

        average_spectrum = np.zeros(len(wavelength_test))
        for measure in range(1, measurement_test + 1):
            average_spectrum = average_spectrum + test_data[:, measure]
        average_spectrum_test = average_spectrum / measurement_test
        return average_spectrum_test, wavelength_test

    def efficencychceck(self, check):
        global test_1, test_2
        self.check_data = load_5
        if check == 'on':
            self.wavelength_test, self.average_spectrum_test = myfunction.check_au(self.wavelength_test,
                                                                                   self.average_spectrum_test,
                                                                                   self.check_data)
            test_1, test_2 = self.average_spectrum_test, self.wavelength_test
            self.ax1.set_title(f"sample:{self.test_filename}", fontsize=10, loc="center")
            self.ax1.plot(self.wavelength_test, self.average_spectrum_test, label=f'Uno.')
        elif check == 'off':
            self.wavelength_test, self.average_spectrum_test = self.wavelength_test, self.average_spectrum_test
            test_1, test_2 = self.average_spectrum_test, self.wavelength_test
            self.ax1.set_title(f"sample:{self.test_filename}", fontsize=10, loc="center")
            self.ax1.plot(self.wavelength_test, self.average_spectrum_test, label=f'Uno.')

    def get_IAgEion(self, specie_name):
        select_specie = self.specie_sheet[self.specie_name.index(specie_name)]
        col_name = []
        for sn in range(select_specie.shape[1]):
            col_name.append(select_specie[0, sn])
        parameter_a = []
        for col_i in range(len(col_name)):
            if col_name[col_i] == 'ion':
                ion = myfunction.getparameter(select_specie, col_name, col_name[col_i])
            else:
                col = myfunction.getparameter(select_specie, col_name, col_name[col_i])
                parameter_a.append(col)
        parameter_a = np.array(parameter_a)
        ssw, A = np.array([np.float64(x) for x in parameter_a[0, :]]), np.array(
            [np.float64(x) for x in parameter_a[1, :]])
        Ek, gk = np.array([np.float64(x) for x in parameter_a[2, :]]), np.array(
            [np.float64(x) for x in parameter_a[3, :]])
        A = A / (10 ** 8)

        dot_rough_test, dotindex_rough_test = myfunction.find_nearest(self.wavelength_test, ssw)
        dotindex_acc_test = myfunction.rough2acc(dotindex_rough_test, self.average_spectrum_test)
        I_test = self.average_spectrum_test[dotindex_acc_test].tolist()
        self.average_spectrum_test_raw = self.average_spectrum_test.copy()
        # 修改后的自吸收校正部分
        if self.checkBox_self_absorption.isChecked():
            try:
                import pandas as pd
                # 单个Excel文件路径
                excel_file_path = "SA/1-1SA.xlsx"

                # 读取指定元素的工作表
                sa_data = pd.read_excel(excel_file_path, sheet_name=specie_name)
                csv_wavelength = sa_data.iloc[:, 0].values  # 第一列是波长
                csv_sa_values = sa_data.iloc[:, 1].values  # 第二列是SA值

                # 为每个谱线索引找到对应的SA值并进行校正
                corrected_intensities = []
                for i, idx in enumerate(dotindex_acc_test):
                    target_wavelength = self.wavelength_test[idx]
                    closest_idx = np.argmin(np.abs(csv_wavelength - target_wavelength))
                    sa_value = csv_sa_values[closest_idx]

                    # 使用强度除以SA值进行校正
                    corrected_intensity = self.average_spectrum_test[idx] / sa_value
                    corrected_intensities.append(corrected_intensity)

                # 更新校正后的强度
                I_test = corrected_intensities
                for i, idx in enumerate(dotindex_acc_test):
                    self.average_spectrum_test[idx] = corrected_intensities[i]

            except Exception as e:
                print(f"元素 {specie_name} 的自吸收校正失败: {e}")
                pass

        I_test_bolz, I_test_saha, testparameter = self.departion(ion, I_test, A, Ek, gk)

        if self.ax1print > 0:
            self.ax1.scatter(self.wavelength_test[dotindex_acc_test],
                             self.average_spectrum_test_raw[dotindex_acc_test],
                             s=30,
                             c=self.color, marker='x',
                             label=f'{specie_name} Line')
            self.ax1.plot(self.wavelength_test, self.average_spectrum_test, '--', color='black', alpha=0.5, zorder=-1)
            self.ax1.set_xlabel('Wavelength (nm)', size=13)
            self.ax1.set_ylabel('Intensity (a.u.)', size=13)
            self.ax1.legend(loc='best', fontsize=8.5)
            self.ax1print = self.ax1print - 1

        return testparameter, I_test_bolz, I_test_saha, dotindex_acc_test, ion
    

    def departion(self, ion, I, A, Ek, gk):
        L = len(ion)
        if 'saha-boltzmann' in ion:
            I_saha, gk_saha, A_saha, Ek_saha = [], [], [], []
            for ion_i in range(L):
                if ion[ion_i] == 'saha-boltzmann':
                    I_saha.append(I[ion_i])
                    gk_saha.append(gk[ion_i])
                    A_saha.append(A[ion_i])
                    Ek_saha.append(Ek[ion_i])
            gk_saha, A_saha, Ek_saha= np.array(gk_saha), np.array(A_saha), np.array(Ek_saha)
        else:
            I_saha = []
            gk_saha, A_saha, Ek_saha = [], [], []

        if 'boltzmann' in ion:
            I_bolz, gk_bolz, A_bolz, Ek_bolz = [], [], [], []
            for ion_i in range(L):
                if ion[ion_i] == 'boltzmann':
                    I_bolz.append(I[ion_i])
                    gk_bolz.append(gk[ion_i])
                    A_bolz.append(A[ion_i])
                    Ek_bolz.append(Ek[ion_i])
            gk_bolz = np.array(gk_bolz)
            A_bolz = np.array(A_bolz)
            Ek_bolz = np.array(Ek_bolz)
        else:
            I_bolz = []
            gk_bolz, A_bolz, Ek_bolz = [], [], []

        # ——返回值依次是选定波长处的平均光谱强度数组，原子谱线强度数组，一次离子谱线强度数组，原子谱线跃迁系数数组，一次离子谱线跃迁系数数组，
        # ——原子谱线简并度数组，一次离子谱线简并度数组，原子谱线上能级能量数组，一次离子谱线上能级能量数组，离子信息数组，—— #
        # ——选定波长对应的测量波长在光谱数据中的索引—— #
        return I_bolz, I_saha, [A_bolz, A_saha, gk_bolz, gk_saha, Ek_bolz, Ek_saha]
    def resultprintout(self):
        self.printout.clear()
        self.printout.appendPlainText(f'定量分析结果：')
        nomalization_factor = 100
        # self.printout.appendPlainText(f'F = {round(F_constant, 3)}')

        for z in range(len(resultcf)):
            self.printout.appendPlainText(f'元素{self.specie_name[z]}的浓度 {round( nomalization_factor * resultcf[z], 4)}%')#归一化

        # for z in range(len(resultcf)):
        #     self.printout.appendPlainText(f"'{self.specie_name[z]}':{round( nomalization_factor * resultcf[z], 4)},")#归一化

        return

    def exist_method(self):
        self.lineEdit.setText('正在退出')
        sys.exit(app.exec_())

class MyFigure(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(16, 9))
        self.fig.subplots_adjust(top=0.92, bottom=0.10, left=0.07, right=0.98)
        plt.rcParams['xtick.direction'] = 'in'
        plt.rcParams['ytick.direction'] = 'in'
        self.fig.canvas.mpl_connect('scroll_event', self.call_scroll)
        self.fig.canvas.mpl_connect('button_press_event', self.call_move)
        self.fig.canvas.mpl_connect('button_release_event', self.call_move)
        self.fig.canvas.mpl_connect('button_press_event', self.call_choose)
        self.fig.canvas.mpl_connect('button_release_event', self.call_choose)
        self.fig.canvas.mpl_connect('motion_notify_event', self.call_move)
        self.fig.canvas.mpl_connect('button_press_event', self.call_initializtion)
        super(MyFigure, self).__init__(self.fig)

    def call_move(self, event):
        global mPress
        global startx
        global starty
        if event.name == 'button_press_event':
            axtemp = event.inaxes
            if axtemp and event.button == 2:
                mPress = True
                startx = event.xdata
                starty = event.ydata
        elif event.name == 'button_release_event':
            axtemp = event.inaxes
            if axtemp and event.button == 2:
                mPress = False
        elif event.name == 'motion_notify_event':
            axtemp = event.inaxes
            if axtemp and event.button == 2 and mPress:
                x_min, x_max = axtemp.get_xlim()
                y_min, y_max = axtemp.get_ylim()
                w = x_max - x_min
                h = y_max - y_min
                mx = event.xdata - startx
                my = event.ydata - starty
                axtemp.set(xlim=(x_min - mx, x_min - mx + w))
                axtemp.set(ylim=(y_min - my, y_min - my + h))
                self.fig.canvas.draw_idle()

    def call_choose(self, event):
        global point0
        if event.button == 1:
            if event.name == 'button_press_event':
                startx0 = event.xdata
                starty0 = event.ydata
                point0 = [startx0, starty0]
            elif event.name == 'button_release_event':
                startx1 = event.xdata
                starty1 = event.ydata
                point1 = [startx1, starty1]
                axtemp = event.inaxes
                axtemp.set(xlim=[min(point0[0], point1[0]), max(point0[0], point1[0])])
                axtemp.set(ylim=[min(point0[1], point1[1]), max(point0[1], point1[1])])
                self.fig.canvas.draw_idle()
                point0 = [0, 0]

    def call_scroll(self, event):
        axtemp = event.inaxes
        if axtemp:
            x_min, x_max = axtemp.get_xlim()
            y_min, y_max = axtemp.get_ylim()
            w = x_max - x_min
            h = y_max - y_min
            curx = event.xdata
            cury = event.ydata
            curXposition = (curx - x_min) / w
            curYposition = (cury - y_min) / h
            if event.button == 'down':
                w = w * 1.1
                h = h * 1.1
            elif event.button == 'up':
                w = w / 1.1
                h = h / 1.1
            newx = curx - w * curXposition
            newy = cury - h * curYposition
            axtemp.set(xlim=(newx, newx + w))
            axtemp.set(ylim=(newy, newy + h))
            self.fig.canvas.draw_idle()

    def call_initializtion(self, event):
        if event.name == 'button_press_event':
            axtemp = event.inaxes
            if event.button == 3:
                if axtemp:

                    xlim0 = axtemp.get_xlim()
                    ylim0 = axtemp.get_ylim()
                    axtemp.set_xlim(xlim0)
                    axtemp.set_ylim(ylim0)
                    self.fig.canvas.draw_idle()

class OtherFigure(FigureCanvas):
    def __init__(self):
        self.fig2 = Figure(figsize=(16, 10))
        self.fig2.subplots_adjust(top=0.96, bottom=0.17, left=0.14, right=0.92)
        plt.rcParams['xtick.direction'] = 'in'
        plt.rcParams['ytick.direction'] = 'in'
        super(OtherFigure, self).__init__(self.fig2)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = Mywindow()
    window.show()
    sys.exit(app.exec_())