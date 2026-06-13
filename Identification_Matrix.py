#该文件用于绘图
#用于存储和处理识别矩阵并且生成对应图表
#主要内容 漏检：黄色圆圈  正确识别：绿色圆圈  错误识别：红色圆圈
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
from difflib import SequenceMatcher

#二维列表转化为0/1矩阵
#调用提示：table可以是列表或者dataframe，table_name是字符串，用于错误提示
def _table_to_dataframe(table, table_name):


    if isinstance(table, pd.DataFrame): #如果输入是DataFrame，直接处理
        # 情况1: 原始CSV样式（默认RangeIndex，第一列是样本名）
        if isinstance(table.index, pd.RangeIndex):
            if table.shape[1] < 2: #检查列数
                raise ValueError(f"{table_name} 的 DataFrame 至少需要包含样本列和一个元素列")
            sample_names = table.iloc[:, 0].tolist()
            df = pd.DataFrame(table.iloc[:, 1:].values, index=sample_names, columns=table.columns[1:]) #index为样本名，columns为元素名
        # 情况2: 已经是矩阵样式（index是样本名，columns是元素名）
        else:
            df = table.copy()
    else:
        if not isinstance(table, (list, tuple)) or len(table) < 2:
            raise ValueError(f"{table_name} 必须是至少包含表头和一行数据的二维列表")

        header = table[0]
        if len(header) < 2:
            raise ValueError(f"{table_name} 的表头至少需要包含样本列和一个元素列")

        sample_names = []
        values = []
        expected_len = len(header)

        for row_id, row in enumerate(table[1:], start=2):
            if len(row) != expected_len:
                raise ValueError(
                    f"{table_name} 第 {row_id} 行长度为 {len(row)}，应为 {expected_len}"
                )
            sample_names.append(row[0])
            values.append(row[1:])

        df = pd.DataFrame(values, index=sample_names, columns=header[1:])

    # 非零都视为“检测到”，零或空值视为“未检测到”
    df = df.fillna(0)
    df = df.apply(pd.to_numeric, errors="coerce").fillna(0)
    df = (df != 0).astype(int)

    # 统一标签，避免空格导致的“伪重复”
    df.index = df.index.map(lambda x: str(x).strip())
    df.columns = df.columns.map(lambda x: str(x).strip())

    # 处理重复样本名和重复元素名：按“检测到优先”规则取 max
    if not df.index.is_unique:
        df = df.groupby(level=0).max()
    if not df.columns.is_unique:
        df = df.T.groupby(level=0).max().T

    return df


def _plot_identification_matrix(matrix, sample_names, element_names):
    """
    绘制识别矩阵：
    2: 漏检(黄), 1: 正确(绿), -1: 错误(红), 0: 无事件(不画)
    """
    #建立画布
    fig, ax = plt.subplots(figsize=(max(8, len(element_names) * 0.6), max(5, len(sample_names) * 0.5)))

    #颜色规则
    color_map = {
        2: "gold",         # 漏检
        1: "limegreen",    # 正确识别
        -1: "red",         # 错误识别
    }

    #逻辑判决
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            value = matrix[i, j]
            if value in color_map:
                ax.scatter(j, i, s=160, c=color_map[value], edgecolors="black")

    #表头和标签
    ax.set_xticks(np.arange(len(element_names)))
    ax.set_xticklabels(element_names, fontsize=15, fontweight="semibold")
    ax.set_yticks(np.arange(len(sample_names)))
    display_sample_labels = [f"{i + 1}" for i in range(len(sample_names))]
    ax.set_yticklabels(display_sample_labels, fontsize=15, fontweight="semibold")
    ax.tick_params(axis="both", which="major", length=0)

    #标签
    ax.set_xlabel("Element", fontsize=15, fontweight="semibold")
    ax.set_ylabel("Sample", fontsize=15, fontweight="semibold")
    ax.set_title("Identification Matrix", fontsize=20, fontweight="semibold")

    # 表格样式：实线单元格边界，圆点位于单元格中心
    ax.set_xlim(-0.5, len(element_names) - 0.5)
    ax.set_ylim(-0.5, len(sample_names) - 0.5)
    ax.invert_yaxis()
    ax.set_xticks(np.arange(-0.5, len(element_names), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(sample_names), 1), minor=True)
    ax.grid(False)
    ax.grid(which="minor", linestyle="-", linewidth=1.5, color="black", alpha=0.7)
    ax.tick_params(which="minor", bottom=False, left=False)
    for spine in ax.spines.values():
        spine.set_linewidth(2.0)

    #图例
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="gold", markeredgecolor="black", markersize=8, label="Neglected"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="limegreen", markeredgecolor="black", markersize=8, label="True"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="red", markeredgecolor="black", markersize=8, label="False"),
    ]

    ax.legend(handles=handles, loc="upper right",  prop={"weight": "semibold", "size": 12})
    for spine in ax.spines.values():
        spine.set_linewidth(2.0)
    plt.tight_layout()
    plt.show()


def _plot_element_metrics(gt_aligned, pred_aligned, element_names):
    """
    绘制按元素统计的 Precision / Recall / F1-score 柱状图（百分比）。
    """
    gt_vals = gt_aligned.values
    pred_vals = pred_aligned.values

    tp = np.sum((gt_vals == 1) & (pred_vals == 1), axis=0)
    fp = np.sum((gt_vals == 0) & (pred_vals == 1), axis=0)
    fn = np.sum((gt_vals == 1) & (pred_vals == 0), axis=0)

    precision = np.divide(tp, tp + fp, out=np.zeros_like(tp, dtype=float), where=(tp + fp) != 0)
    recall = np.divide(tp, tp + fn, out=np.zeros_like(tp, dtype=float), where=(tp + fn) != 0)
    f1 = np.divide(
        2 * precision * recall,
        precision + recall,
        out=np.zeros_like(precision, dtype=float),
        where=(precision + recall) != 0,
    )

    precision_pct = precision * 100
    recall_pct = recall * 100
    f1_pct = f1 * 100


    #柱状图图形设置
    group_step = 1.25  # 控制“元素组与元素组”之间间距，越大越分开
    x = np.arange(len(element_names)) * group_step
    width = 0.25
    gap = 0.04
    offset = width + gap

    fig, ax = plt.subplots(figsize=(max(8, len(element_names) * 1), 6))
    ax.bar(x - offset, precision_pct, width=width, color="royalblue", label="Precision")
    ax.bar(x, recall_pct, width=width, color="limegreen", label="Recall")
    ax.bar(x + offset, f1_pct, width=width, color="gold", label="F1-score")

    ax.set_xticks(x)
    ax.set_xticklabels(element_names, ha="right", fontsize=15, fontweight="semibold")
    ax.set_xlabel("Element", fontsize=15, fontweight="semibold")

    ax.set_ylabel("Percentage", fontsize=15, fontweight="semibold")
    ax.set_title("Precision / Recall / F1-score", fontsize=20, fontweight="semibold")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda val, pos: f"{val:.0f}%"))
    ax.tick_params(axis="y", labelsize=15)
    for lab in ax.get_yticklabels():
        lab.set_fontweight("semibold")
        lab.set_ha("right")
    ax.tick_params(axis="both", which="major", top=True,right=True,length=0)
    ax.grid(False)
    ax.set_ylim(0, 110)

    for spine in ax.spines.values():
        spine.set_linewidth(1.8)
    for label in ax.get_yticklabels():
        label.set_fontweight("semibold")

    ax.legend(loc="upper right",  prop={"weight": "semibold", "size": 12})

    plt.tight_layout()
    plt.show()


def generate_identification_matrix(contents_df, predictions, show_plot=True, show_metrics_plot=True):
    """
    生成识别矩阵：
    contents_df是样本含量的0/1矩阵
    pred_df是算法检测的0/1矩阵

    对齐策略：
    1) 若行列名有交集，按交集对齐；
    2) 若名称完全对不上，按位置对齐（避免 union 导致行列翻倍）。
    """

    contents_df = _table_to_dataframe(contents_df, "contents")
    pred_df = _table_to_dataframe(predictions, "confidence")

    # 按需求裁掉最后四列
    if contents_df.shape[1] <= 4 or pred_df.shape[1] <= 4:
        raise ValueError("contents_df 或 predictions 的列数不足，无法裁掉最后四列")
    contents_df = contents_df.iloc[:, :-4]
    pred_df = pred_df.iloc[:, :-4]

    # 自动对齐：优先按交集对齐；若名称完全不匹配则按位置对齐
    common_samples = list(contents_df.index.intersection(pred_df.index))
    common_elements = list(contents_df.columns.intersection(pred_df.columns))

    use_name_alignment = (len(common_samples) > 0) and (len(common_elements) > 0)

    if use_name_alignment:
        sample_names = common_samples
        element_names = common_elements
        gt_aligned = contents_df.reindex(index=sample_names, columns=element_names, fill_value=0)
        pred_aligned = pred_df.reindex(index=sample_names, columns=element_names, fill_value=0)
    else:
        n_rows = min(len(contents_df.index), len(pred_df.index))
        n_cols = min(len(contents_df.columns), len(pred_df.columns))
        if n_rows == 0 or n_cols == 0:
            raise ValueError("contents_df 和 predictions 无法对齐：有效行或列数量为 0")

        gt_aligned = contents_df.iloc[:n_rows, :n_cols].copy()
        pred_aligned = pred_df.iloc[:n_rows, :n_cols].copy()

        # 统一标签，保证后续绘图和返回值一致
        sample_names = pred_aligned.index.tolist()
        element_names = pred_aligned.columns.tolist()
        gt_aligned.index = sample_names
        gt_aligned.columns = element_names

    matrix = np.zeros(gt_aligned.shape, dtype=int)

    gt_vals = gt_aligned.values
    pred_vals = pred_aligned.values

    # 正确识别: 真=1, 预测=1
    matrix[(gt_vals == 1) & (pred_vals == 1)] = 1
    # 漏检: 真=1, 预测=0
    matrix[(gt_vals == 1) & (pred_vals == 0)] = 2
    # 错误识别: 真=0, 预测=1
    matrix[(gt_vals == 0) & (pred_vals == 1)] = -1

    if show_plot:
        _plot_identification_matrix(matrix, sample_names, element_names)

    if show_metrics_plot:
        _plot_element_metrics(gt_aligned, pred_aligned, element_names)

    return matrix, sample_names, element_names


#整套模式
filepath = r'D:\LIBS\RREdetectation\Confidence_debug\T_scanoff\Pt5'
confidence_path=os.path.join(filepath,'rareearth_confidence_results.csv')
contents_path=os.path.join(filepath,'Randomrareearth_contents.csv')
confidence=pd.read_csv(confidence_path)
contents=pd.read_csv(contents_path)
identification_matrix, sample_names, element_names = generate_identification_matrix(contents, confidence, show_plot=True, show_metrics_plot=True)


# #对应样本模式
# filepath2=r'D:\LIBS\RREdetectation\RandomSpectrum'
# target_file=['03116']
# target_name = str(target_file[0]).strip()


# def _normalize_sample_name(name):
#     s = str(name).strip().lower()
#     if s.endswith('.csv'):
#         s = s[:-4]
#     return s


# def _name_match_score(candidate, target):
#     candidate_norm = _normalize_sample_name(candidate)
#     target_norm = _normalize_sample_name(target)

#     if candidate_norm == target_norm:
#         return 1.0
#     if candidate_norm.startswith(target_norm) or target_norm.startswith(candidate_norm):
#         return 0.95

#     prefix_len = len(os.path.commonprefix([candidate_norm, target_norm]))
#     prefix_ratio = prefix_len / max(1, min(len(candidate_norm), len(target_norm)))
#     similarity = SequenceMatcher(None, candidate_norm, target_norm).ratio()
#     return max(similarity, prefix_ratio * 0.9)


# def _select_best_matched_row(df, target, min_score=0.6):
#     if df.empty:
#         return df.copy()

#     first_col = df.iloc[:, 0].astype(str)
#     scores = first_col.map(lambda x: _name_match_score(x, target))
#     best_idx = scores.idxmax()
#     best_score = float(scores.loc[best_idx])

#     if best_score < min_score:
#         return df.iloc[0:0].copy()
#     return df.loc[[best_idx]].copy()

# confidence_rows = []
# contents_rows = []

# for i in range(1, 26):
#     pt_folder = f'Pt{i}'
#     confidence_path=os.path.join(filepath2, pt_folder, 'rareearth_confidence_results.csv')
#     contents_path=os.path.join(filepath2, pt_folder, 'Randomrareearth_contents.csv')
#     confidence_origin=pd.read_csv(confidence_path)
#     contents_origin=pd.read_csv(contents_path)


#     # 只保留与 target_file 最相近的一行（支持前缀/相似匹配）
#     confidence = _select_best_matched_row(confidence_origin, target_name)
#     contents = _select_best_matched_row(contents_origin, target_name)
    

#     if confidence.empty or contents.empty:
#         print(f"Pt{i}: 未找到目标样本 {target_name}，已跳过")
#         continue

#     # 为避免不同文件中同名样本被后续聚合，增加 Pt 编号前缀
#     unique_sample_name = f"Pt{i}_{target_name}"
#     confidence.iloc[:, 0] = unique_sample_name
#     contents.iloc[:, 0] = unique_sample_name

#     confidence_rows.append(confidence)
#     contents_rows.append(contents)

# if not confidence_rows or not contents_rows:
#     raise ValueError(f"在 Pt1~Pt25 中未找到目标样本 {target_name}")

# confidence_all = pd.concat(confidence_rows, axis=0, ignore_index=True)
# contents_all = pd.concat(contents_rows, axis=0, ignore_index=True)
# identification_matrix, sample_names, element_names = generate_identification_matrix(
#     contents_all,
#     confidence_all,
#     show_plot=True,
#     show_metrics_plot=True,
# )
    