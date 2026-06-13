from simLIBS import SimulatedLIBS
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import os
import time
import traceback


contents=pd.read_csv(r"D:\LIBS\RREdetectation\SimspecGen\saved\contents.csv")
FLAG_COLUMN = "generated_flag"

if FLAG_COLUMN not in contents.columns:
    contents[FLAG_COLUMN] = ""


def get_pending_count():
    return int((contents[FLAG_COLUMN].astype(str).str.strip().str.upper() != 'G').sum())

#参数说明： mode有geneate、debug和random三种，generate模式会生成contents.csv中所有的光谱文件，debug模式会指定文件并且打开浏览器
#random则是会生成随机种类和含量的随机模拟光谱
def generate_spectra(mode,file_name,resolution=3000,Te=0.5,Ne=1e17,low_w=200,upper_w=900):
    if mode=='generate':
        pending_indices = [i for i in range(len(contents)) if str(contents.at[i, FLAG_COLUMN]).strip().upper() != 'G']
        total_pending = len(pending_indices)
        print(f"待生成光谱数量: {total_pending}")
        print(f"分辨率为：{resolution}, Te={Te} eV, Ne={Ne} cm^-3, 波长范围: {low_w}-{upper_w} nm")

        if total_pending == 0:
            print("所有光谱都已生成，无需处理。")
            return

        completed_now = 0
        for i in pending_indices:

            elements_main=['Si', 'Al', 'Fe','Ca','K','Na','Mg','Cr','Cu','Mn','Zn','Ti','Ni','Mo','C','Li','Pb']
            elements_rareearth=['Y', 'Eu', 'Lu', 'Er', 'Ho', 'Yb', 'La', 'Tm','Tb', 'Sm', 'Pr']
            elements=elements_main + elements_rareearth
            file_name=contents.iloc[i, 0]
            file_name = str(contents.iloc[i, 0]).removeprefix("GBW")
            main_columns = [f"{element}_at%" for element in elements_main]
            percentages_main = [contents.at[i, column] for column in main_columns]
            percentages_rareearth=[0.4545,0.4545,0.4545,0.4545,0.4545,0.4545,0.4545,0.4545,0.4545,0.4545,0.4545] 
            percentages=percentages_main + percentages_rareearth  

                # Remove elements with zero percentage
            elements = [elem for elem, perc in zip(elements, percentages) if perc > 0]
            percentages = [perc for perc in percentages if perc > 0]

            if len(percentages) > 0:
                percentages[-1] = 100.0 - sum(percentages[:-1])

            libs = SimulatedLIBS(
                Te=Te,
                Ne=Ne,
                elements=elements,
                percentages=percentages,
                resolution=resolution,
                low_w=low_w,
                upper_w=upper_w,
                max_ion_charge=2,
                webscraping='dynamic',
                headless=True,
                keep_browser_open=False,
                detach_browser=False
            )
            save_dir = r"D:\LIBS\RREdetectation\SimspecGen\saved"
            libs.save_to_csv(os.path.join(save_dir, file_name + "_95.csv"))
            contents.at[i, FLAG_COLUMN] = 'G'
            contents.to_csv(r"D:\LIBS\RREdetectation\SimspecGen\saved\contents.csv", index=False)
            completed_now += 1
            print( f'{file_name}_95.csv',"saved successfully.")
            print(f"当前进度: {completed_now}/{total_pending}")
            delay = 5  # 设置延迟时间，单位为秒

        print(f"本次生成完成，共处理: {completed_now}/{total_pending}")

    elif mode=='debug':
        if file_name is None:
            print("请提供要调试的文件路径")
            return
        elements_main=['Si', 'Al', 'Fe','Ca','K','Na','Mg','Cr','Cu','Mn','Zn','Ti','Ni','Mo','C','Li','Pb']
        elements_rareearth=['Y', 'Eu', 'Lu', 'Er', 'Ho', 'Yb', 'La', 'Tm','Tb', 'Sm', 'Pr']
        elements=elements_main + elements_rareearth
        if not file_name.startswith("GBW"):
            file_name = "GBW" + file_name
        matched = contents[contents.iloc[:, 0] == file_name]
        main_columns = [f"{element}_at%" for element in elements_main]
        percentages_main = matched.loc[matched.index[0], main_columns].tolist()
        percentages_rareearth=[0,0.9061488546224832,0.0061395194995659,0,0,0.4230829159791232,0,0.6444894415024695,0.2754599537149959,0,2.744679314681362
] 
        
        percentages=percentages_main + percentages_rareearth  

            # Remove elements with zero percentage
        elements = [elem for elem, perc in zip(elements, percentages) if perc > 0]
        percentages = [perc for perc in percentages if perc > 0]

        if len(percentages) > 0:
            percentages[-1] = 100.0 - sum(percentages[:-1])

        libs = SimulatedLIBS(
            Te=Te,
            Ne=Ne,
            elements=elements,
            percentages=percentages,
            resolution=resolution,
            low_w=low_w,
            upper_w=upper_w,
            max_ion_charge=2,
            webscraping='dynamic',
            headless=False,
            keep_browser_open=True,
            detach_browser=True
        )
        delay = 5  # 设置延迟时间，单位为秒

    elif mode=='random':#基体元素相同，但是稀土元素数量与含量随机
        pending_indices = [i for i in range(len(contents)) if str(contents.at[i, FLAG_COLUMN]).strip().upper() != 'G']
        total_pending = len(pending_indices)
        print(f"待生成光谱数量: {total_pending}")
        print(f"分辨率为：{resolution}, Ne={Ne} cm^-3, 波长范围: {low_w}-{upper_w} nm")

        if total_pending == 0:
            print("所有光谱都已生成，无需处理。")
            return
        
        save_dir = r"D:\LIBS\RREdetectation\SimspecGen\saved"
        RAREEARTH_FIXED_ORDER = ['Y', 'Eu', 'Lu', 'Er', 'Ho', 'Yb', 'La', 'Tm','Tb', 'Sm', 'Pr','Ce','Nd','Dy','Gd']
        confidence_csv_path = os.path.join(save_dir, 'Randomrareearth_contents.csv')
        confidence_columns = ['file_name'] + [f"{elem}_at%" for elem in RAREEARTH_FIXED_ORDER] + ['Te_eV']

        completed_now = 0
        for i in pending_indices:
            elements_main=['Si', 'Al', 'Fe','Ca','K','Na','Mg','Cr','Cu','Mn','Zn','Ti','Ni','Mo','C','Li','Pb']
            elements_rareearth=['Y', 'Eu', 'Lu', 'Er', 'Ho', 'Yb', 'La', 'Tm','Tb', 'Sm', 'Pr']
            te_random = float(np.random.uniform(0.65, 1.05))
            file_name=contents.iloc[i, 0]
            file_name = str(contents.iloc[i, 0]).removeprefix("GBW")
            main_columns = [f"{element}_at%" for element in elements_main]
            percentages_main = [contents.at[i, column] for column in main_columns]
            num_rareearth = np.random.randint(1, len(elements_rareearth) + 1)
            selected_rareearth = np.random.choice(elements_rareearth, size=num_rareearth, replace=False).tolist()
            remaining_pct = max(0.0, 100.0 - float(sum(percentages_main)))
            percentages_rareearth = np.random.dirichlet(np.ones(num_rareearth)) * remaining_pct
            rareearth_pct_map = {elem: 0.0 for elem in RAREEARTH_FIXED_ORDER}#字典
            for elem, pct in zip(selected_rareearth, percentages_rareearth):
                rareearth_pct_map[elem] = float(pct)

            elements = elements_main + selected_rareearth
            percentages = percentages_main + percentages_rareearth.tolist()
        

                        # Remove elements with zero percentage
            elements = [elem for elem, perc in zip(elements, percentages) if perc > 0]
            percentages = [perc for perc in percentages if perc > 0]

            if len(percentages) > 0:
                percentages[-1] = 100.0 - sum(percentages[:-1])

            libs = SimulatedLIBS(
                Te=te_random,
                Ne=Ne,
                elements=elements,
                percentages=percentages,
                resolution=resolution,
                low_w=low_w,
                upper_w=upper_w,
                max_ion_charge=2,
                webscraping='dynamic',
                headless=True,
                keep_browser_open=False,
                detach_browser=False
            )
            libs.save_to_csv(os.path.join(save_dir, file_name + "_95_random.csv"))
            contents.at[i, FLAG_COLUMN] = 'G'
            contents.to_csv(r"D:\LIBS\RREdetectation\SimspecGen\saved\contents.csv", index=False)
            completed_now += 1

            confidence_row = {'file_name': file_name + "_95_random.csv"}
            for elem in RAREEARTH_FIXED_ORDER:
                confidence_row[f"{elem}_at%"] = rareearth_pct_map[elem]
            confidence_row['Te_eV'] = te_random*11604  # 将Te从eV转换为K

            current_row_df = pd.DataFrame([confidence_row], columns=confidence_columns)
            if os.path.exists(confidence_csv_path):
                existing_records = pd.read_csv(confidence_csv_path)
                all_records = pd.concat([existing_records, current_row_df], ignore_index=True)
                all_records = all_records.drop_duplicates(subset=['file_name'], keep='last')
                all_records = all_records.reindex(columns=confidence_columns)
                all_records.to_csv(confidence_csv_path, index=False)
            else:
                current_row_df.to_csv(confidence_csv_path, index=False)

            print( f'{file_name}_95_random.csv',"saved successfully.")
            print(f"本条样本随机Te: {te_random*11604:.4f} K")
            print(f"当前进度: {completed_now}/{total_pending}")
            delay = 5  # 设置延迟时间，单位为秒

        print(f"本次生成完成，共处理: {completed_now}/{total_pending}")



#防中断程序
def run_generate_with_auto_restart(retry_wait_seconds=10,mode='generate',file_name=None):
    while True:
        pending_before = get_pending_count()
        if pending_before == 0:
            print("所有任务已完成，程序结束。")
            break

        print(f"检测到剩余任务 {pending_before} 条，开始运行生成任务。")
        try:
            generate_spectra(mode=mode,file_name=file_name,resolution=3000,Te=1.5,Ne=1e17,low_w=200,upper_w=900)
            pending_after = get_pending_count()
            if pending_after == 0:
                print("本轮运行后所有任务已完成。")
                break
            print(f"本轮结束后仍有 {pending_after} 条未完成，将继续下一轮。")
        except KeyboardInterrupt:
            print("检测到手动中断，程序退出。")
            break
        except Exception as error:
            print(f"检测到程序中断: {error}")
            traceback.print_exc()
            print(f"{retry_wait_seconds} 秒后自动重试...")
            time.sleep(retry_wait_seconds)


generate_spectra(mode='debug',file_name="070101",resolution=3000,Te=0.86,Ne=1e17,low_w=300,upper_w=900)
# run_generate_with_auto_restart(retry_wait_seconds=10,mode='debug',file_name="070099")
