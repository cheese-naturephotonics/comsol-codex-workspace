from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import glob
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)

OUTPUT = Path(__file__).resolve().parent / "output" / "Helix_LP_OAM_Figure_Issue_Checklist_CN.pdf"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def register_fonts() -> tuple[str, str]:
    regular_candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]
    bold_candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.otf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]
    regular = next((p for p in regular_candidates if os.path.exists(p)), None)
    bold = next((p for p in bold_candidates if os.path.exists(p)), None)
    if regular is None:
        candidates = glob.glob("/usr/share/fonts/**/*CJK*Regular*.*", recursive=True)
        regular = candidates[0] if candidates else None
    if bold is None:
        candidates = glob.glob("/usr/share/fonts/**/*CJK*Bold*.*", recursive=True)
        bold = candidates[0] if candidates else regular
    if regular is None:
        raise RuntimeError("No CJK font found. Install fonts-noto-cjk.")
    pdfmetrics.registerFont(TTFont("CJK", regular, subfontIndex=0))
    pdfmetrics.registerFont(TTFont("CJK-Bold", bold or regular, subfontIndex=0))
    return "CJK", "CJK-Bold"


FONT, FONT_BOLD = register_fonts()
PAGE_SIZE = landscape(A4)
PAGE_W, PAGE_H = PAGE_SIZE


@dataclass(frozen=True)
class Issue:
    priority: str
    problem: str
    action: str
    acceptance: str


PRIORITY_LABEL = {
    "P0": "P0｜投稿前必须修正",
    "P1": "P1｜科学证据应补齐",
    "P2": "P2｜排版与可读性优化",
}
PRIORITY_COLOR = {
    "P0": colors.HexColor("#FDE2E2"),
    "P1": colors.HexColor("#FFF1CC"),
    "P2": colors.HexColor("#EEF2F5"),
}
DARK = colors.HexColor("#243447")
MID = colors.HexColor("#52697A")
ACCENT = colors.HexColor("#1D6F8A")
LIGHT = colors.HexColor("#F7F9FA")
LINE = colors.HexColor("#CBD5DC")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="TitleCN", fontName=FONT_BOLD, fontSize=23, leading=30,
    alignment=TA_CENTER, textColor=DARK, spaceAfter=8*mm,
))
styles.add(ParagraphStyle(
    name="SubtitleCN", fontName=FONT, fontSize=11, leading=17,
    alignment=TA_CENTER, textColor=MID, spaceAfter=5*mm,
))
styles.add(ParagraphStyle(
    name="H1CN", fontName=FONT_BOLD, fontSize=16, leading=22,
    textColor=DARK, spaceBefore=2*mm, spaceAfter=4*mm,
))
styles.add(ParagraphStyle(
    name="H2CN", fontName=FONT_BOLD, fontSize=12.5, leading=18,
    textColor=ACCENT, spaceBefore=2*mm, spaceAfter=2.5*mm,
))
styles.add(ParagraphStyle(
    name="BodyCN", fontName=FONT, fontSize=9.3, leading=14.2,
    textColor=colors.HexColor("#20272C"), spaceAfter=2.2*mm,
))
styles.add(ParagraphStyle(
    name="SmallCN", fontName=FONT, fontSize=7.7, leading=11,
    textColor=colors.HexColor("#344149"),
))
styles.add(ParagraphStyle(
    name="TableHeaderCN", fontName=FONT_BOLD, fontSize=8.0, leading=10.4,
    textColor=colors.white, alignment=TA_CENTER,
))
styles.add(ParagraphStyle(
    name="TableCN", fontName=FONT, fontSize=7.7, leading=10.6,
    textColor=colors.HexColor("#20272C"),
))
styles.add(ParagraphStyle(
    name="CalloutCN", fontName=FONT_BOLD, fontSize=10.5, leading=16,
    textColor=colors.HexColor("#7A1E1E"), backColor=colors.HexColor("#FFF4F4"),
    borderColor=colors.HexColor("#E5A5A5"), borderWidth=0.7,
    borderPadding=8, spaceBefore=2*mm, spaceAfter=4*mm,
))
styles.add(ParagraphStyle(
    name="EquationCN", fontName=FONT, fontSize=10, leading=15,
    alignment=TA_CENTER, textColor=DARK, backColor=LIGHT,
    borderColor=LINE, borderWidth=0.5, borderPadding=7,
    spaceBefore=2*mm, spaceAfter=3*mm,
))


def P(text: str, style: str = "BodyCN") -> Paragraph:
    return Paragraph(text, styles[style])


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.4)
    canvas.line(14*mm, 11*mm, PAGE_W-14*mm, 11*mm)
    canvas.setFont(FONT, 7.2)
    canvas.setFillColor(MID)
    canvas.drawString(14*mm, 6.7*mm, "螺旋 LP/OAM 论文图件问题总清单｜2026-09-06")
    canvas.drawRightString(PAGE_W-14*mm, 6.7*mm, f"第 {doc.page} 页")
    canvas.restoreState()


class ReviewDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str):
        super().__init__(
            filename,
            pagesize=PAGE_SIZE,
            rightMargin=14*mm,
            leftMargin=14*mm,
            topMargin=13*mm,
            bottomMargin=15*mm,
            title="螺旋 LP/OAM 论文图件问题总清单与修改验收表",
            author="OpenAI",
            subject="Figure review checklist",
        )
        frame = Frame(
            self.leftMargin, self.bottomMargin,
            self.width, self.height,
            id="normal",
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )
        self.addPageTemplates([PageTemplate(id="review", frames=[frame], onPage=footer)])


def issue_table(issues: Iterable[Issue], col_widths=None) -> Table:
    issues = list(issues)
    data = [[
        P("优先级", "TableHeaderCN"),
        P("发现的问题", "TableHeaderCN"),
        P("建议修改", "TableHeaderCN"),
        P("验收标准", "TableHeaderCN"),
        P("完成", "TableHeaderCN"),
    ]]
    for issue in issues:
        data.append([
            P(PRIORITY_LABEL[issue.priority], "TableCN"),
            P(issue.problem, "TableCN"),
            P(issue.action, "TableCN"),
            P(issue.acceptance, "TableCN"),
            P("□", "TableCN"),
        ])
    widths = col_widths or [32*mm, 72*mm, 82*mm, 68*mm, 11*mm]
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for row, issue in enumerate(issues, start=1):
        style.append(("BACKGROUND", (0, row), (0, row), PRIORITY_COLOR[issue.priority]))
        if row % 2 == 0:
            style.append(("BACKGROUND", (1, row), (-1, row), colors.HexColor("#FBFCFD")))
    table.setStyle(TableStyle(style))
    return table


def summary_table(rows: list[tuple[str, str, str, str]]) -> Table:
    data = [[
        P("图件", "TableHeaderCN"), P("建议定位", "TableHeaderCN"),
        P("核心结论", "TableHeaderCN"), P("主要风险", "TableHeaderCN"),
    ]]
    for r in rows:
        data.append([P(x, "TableCN") for x in r])
    table = Table(data, colWidths=[42*mm, 42*mm, 102*mm, 78*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFB")]),
    ]))
    return table


GLOBAL_ISSUES = [
    Issue("P0", "角度符号混用：结构机械角、LP 图样物理角、系数空间角和 Bloch 角多处均写成 Δθ。", "全文固定：Θ(z) 为结构机械方位；δ 为 LP 图样物理旋转；η=2ℓδ 为 R_y 的 Bloch 角；ζ=φ_b−φ_a 为 R_z 相位角。", "任一图中的角度均可由 caption 唯一判断，且不存在同一符号跨物理量使用。"),
    Issue("P0", "C_N 的 N 与快螺旋圈数 N 冲突。", "横截面对称阶数保留 N；机械圈数改为 N_turn 或 N_h；快螺旋长度写 L_f=N_turn Λ_h。", "全文搜索 N 后，无一处无法判断其代表对称阶数还是圈数。"),
    Issue("P0", "机械 pitch 与 C_N 图案最短重复周期未区分，可能差 N 倍。", "定义 Λ_h=2π/|K_h| 为标记小圆完整机械 pitch；定义 Λ_pattern=Λ_h/N 为折射率图案最短周期。", "所有长度公式注明使用 Λ_h 或 Λ_pattern；不存在裸写 Λ 的歧义。"),
    Issue("P0", "D1 的 θ_z=φ_b−φ_a 与此前复振幅计算符号相反。", "回到原始复数 t_a、t_b，统一时间/传播相位约定和 a/b 标签；重新生成 D1，并同步修改所有门角符号。", "D1、端口矩阵、OAM 手性相位和 Z–Y–Z Euler 角使用同一符号，数值可交叉复算。"),
    Issue("P0", "多图未说明输入/监测基底是无扰动圆芯标准 LP 端口，还是扰动截面本征模。", "每张功率图和直段图在 caption 明写 input basis、monitor basis、是否有渐变接头。", "读者可判断纯 a/b 恒定功率是本征基底结论还是标准端口结论。"),
    Issue("P0", "conditional、absolute、逐帧强度归一化三种口径未在所有图中明确区分。", "功率图标 P/P_in，并声明是否重归一化；场快照注明逐帧归一化还是统一绝对标尺。", "起点功率不足不再被误读为物理损耗；不同口径不在同一表中混用。"),
    Issue("P0", "T1/T2/T3 命名可能与历史静态 T2 模型混淆。", "统一改为 Model I、Model II、Model III；首次出现写 P、P⊕D、P⊕D⊕C_R。", "全文不存在无法判断 T2 定义的图例。"),
    Issue("P0", "OAM+ 与 OAM− 的强度均为环形，若只画强度不能验证手性与复相位。", "至少为一个代表 OAM 输入增加相位图、相位绕行箭头或 OAM Stokes/Bloch 量；功率分解保留。", "读者能独立判断手性翻转，而不是只依据两个相似环形强度图。"),
    Issue("P0", "ER 图未统一说明分子、分母、数值 floor 和门限，60 dB 尖峰易被误读。", "caption 给出 ER 公式、P_floor、截止掩码和 desired/undesired 模式；加入 20/30 dB 门限和连续带宽。", "任一 ER 数值可由源数据和公式复算。"),
    Issue("P0", "C4–LP11 spectator 图仍标注目标 Δθ=45°，会被理解为旋转失败。", "改为 same C4 device / LP11 spectator / target U_11≈I，并区分器件机械角与该模式输出角。", "图题不再暗示 LP11 应旋转 45°。"),
    Issue("P1", "中螺旋和直段的大量强度结果尚未在图中闭合到共同相位参考下的复数 2×2 传输矩阵。", "在主文或补充表中加入 T、最近酉、指定门匹配度、目标保留率和轴角。", "六态图与同一固定器件的复矩阵一致，不能各态独立去整体相位。"),
    Issue("P1", "快螺旋有限参数下可能偏离纯 R_y，但图中主要用旋转角表达。", "增加轴纯度 √(n_x²+n_z²)、指定 R_y 匹配度和 P_ret；必要时采用完整矩阵优化。", "可调范围内同时满足目标角、轴纯度和保留率要求。"),
    Issue("P1", "跨模式块共同相位 χ_ℓ 尚未在多模式架构图中体现。", "声明当前控制为块内 SU(2)；若考虑跨 ℓ 相干，记录并补偿 χ_ℓ−χ_m，或将目标扩展到 U(2)。", "论文结论不把块内 SU(2) 误写成任意跨模式相干控制。"),
    Issue("P2", "BPM 红色与 Model III 橙色过近，缩小后难以区分。", "BPM 改为黑色粗线/实心点；Model I 绿色、II 蓝色、III 橙色，并兼顾线型。", "灰度打印和色觉缺陷条件下仍可辨认。"),
    Issue("P2", "多图信息密度过高，双栏缩放后文字、marker 和场图难以阅读。", "正文每图只承担一个结论；完整六态/多输入/多模型曲线移入补充材料。", "按目标期刊双栏宽度打印后，轴标、图例和场图仍清晰。"),
    Issue("P2", "功率图缺少统一共享纵轴标题，部分仅显示 0–1。", "统一写 Normalized modal power, P/P_in；条件归一化另加 superscript 或注释。", "任何子图脱离正文也能判断纵轴含义。"),
    Issue("P2", "彩色小圆、白色大圆和不同颜色轨迹未在图注解释。", "说明白圆为纤芯边界；彩色圆为等价扰动位置；颜色仅用于轨迹识别且 n_s 相同。", "读者不会误认为不同颜色代表不同材料。"),
]

FIGURES: list[tuple[str, str, str, list[Issue]]] = [
    (
        "结构图 A｜C₁–C₄ 横截面几何",
        "定义 C_N 对称的圆形小扰动及其随 z 的机械方位。",
        "建议作为 Figure 1(a) 的通用几何定义；C₁–C₄ 可缩成 inset。",
        [
            Issue("P0", "θ(z) 没有明确说明是标记参考小圆的方位，且 C_N 图案本身只在模 2π/N 下唯一。", "改为 Θ(z)=Θ₀+K_hz，并写明其代表 labeled reference inclusion；注明 Θ≡Θ+2π/N。", "几何方位定义与所有螺旋长度公式一致。"),
            Issue("P0", "未定义正手性/观察方向。", "caption 明确从 +z 传播方向观察时 K_h>0 对应顺时针或逆时针。", "任意人可由图重建螺旋手性。"),
            Issue("P1", "几何参数 ρ、d_s、R_c 未在图中标出。", "在一个通用 C_N panel 标出小圆中心半径 ρ、小圆直径 d_s、纤芯半径 R_c。", "横截面几何不依赖正文猜测。"),
            Issue("P1", "相邻小圆的角间隔没有公式。", "加入 φ_j(z)=Θ(z)+2πj/N, j=0,…,N−1。", "图与数值几何定义一一对应。"),
            Issue("P2", "不同小圆使用不同颜色，容易被理解为折射率不同。", "caption 明写所有小圆折射率均为 n_s，颜色仅用于标记等价位置。", "颜色不承载材料参数含义。"),
            Issue("P2", "C₁ 只表示无非平凡旋转对称性，易被理解为“一阶旋转对称”。", "第一次出现时说明 C₁ 为单个离轴扰动、仅含恒等对称操作。", "术语符合群对称性含义。"),
        ],
    ),
    (
        "结构图 B｜Slow / Middle / Fast / Straight 四工作区",
        "作为整篇论文的机制地图，区分绝热拖拽、循环返回、快累积和直段相位门。",
        "建议与结构图 A 合并为 Figure 1，并新增 Z–Y–Z 架构小面板。",
        [
            Issue("P0", "L_f=NΛ 中 N 与 C_N 冲突。", "改为 L_f=N_turnΛ_h。", "所有 N 均无歧义。"),
            Issue("P0", "四个 panel 都使用 Δθ，未区分结构机械角与模式输出角。", "结构角用 ΔΘ_mech；LP 物理输出角用 δ；Bloch 角用 η=2ℓδ。", "慢/中/快的角度关系可直接比较。"),
            Issue("P0", "快螺旋写 Δθ(Δβ)，对 C4–LP11 等直接分裂为零但仍有动态响应的 case 不普适。", "改为 δ_fast=q_effL_f 或 δ_fast(N,ρ,n_s,Λ_h,L_f,λ,…）。", "公式覆盖三个模型和名义禁戒高阶响应。"),
            Issue("P0", "直结构只写 Λ→∞，没有显示其核心功能。", "加入 K_h=0、ζ=(β_a−β_b)L、U_str=R_z^(LP)(ζ)≡R_x^(OAM)(ζ)。", "读者无需看后文即可理解直段是 Z 门。"),
            Issue("P1", "慢螺旋未限定 branch-aligned input。", "写 adiabatic eigenbranch following / branch-aligned input，并注明 δ_slow≈ΔΘ_mech。", "不再暗示任意复输入都自动得到宽带 R_y。"),
            Issue("P1", "中螺旋未显示循环返回条件。", "加入 cyclic return: GL_m=2πM；输出关系仅在返回点成立。", "中螺旋与普通“中等速度”清楚区分。"),
            Issue("P1", "0°/90° a/b 示例只适用于 LP11。", "注明 LP11 shown for illustration；一般正交 LP 方位差为 π/(2ℓ)。", "图可推广到 LP21 等模式而不出错。"),
            Issue("P1", "尚未显示最终统一器件架构。", "增加 Z_L–Y–Z_R panel；每层含 C₂,C₄,…,C₂ℓmax 选择单元。", "Figure 1 能自然引出块选择型 SU(2)。"),
            Issue("P2", "四个工作区名称不够醒目。", "每个 panel 顶部直接写 Slow helix、Middle helix、Fast helix、Straight section。", "读者可在数秒内把图与正文分节对应。"),
        ],
    ),
    (
        "S2｜慢螺旋功率、场图与 ER 光谱",
        "展示 C2/C4 对 LP11/LP21 的慢绝热拖拽、spectator 行为和光谱 ER。",
        "完整版适合 Supplementary；正文抽取 2–3 个代表 case 与一个带宽总结。",
        [
            Issue("P0", "右列标题写 ER bandwidth，但实际画的是 ER(λ)，未给门限带宽。", "改为 Spectral extinction ratio；加入 20/30 dB 水平门限和满足门限的连续波段。", "标题、曲线和报告的带宽定义一致。"),
            Issue("P0", "60 dB 尖峰未说明是否由功率 floor 截断。", "给出 ER 公式、P_floor、desired/undesired 模式和截止掩码。", "尖峰不会被误解成实测无限消光。"),
            Issue("P0", "C4–LP11 panel 仍写 Δθ=+45°。", "改为 LP11 spectator in the same C4 device；另写器件机械总角。", "不暗示 LP11 目标为 45°。"),
            Issue("P1", "光谱扫描是否包含材料色散、模式截止和端口变化未写清。", "caption 声明折射率是否固定、如何处理截止、各波长输入/分析端口如何定义。", "带宽结论边界明确。"),
            Issue("P1", "场图与功率曲线的归一化口径未在图内说明。", "注明快照是否逐帧归一化；功率曲线保持 P/P_in。", "形状展示与绝对功率证据不混淆。"),
            Issue("P2", "八行曲线、四十张场图和八个 ER panel 过密。", "正文只保留 C2–LP11、C4–LP21、C4–LP11 spectator；完整矩阵移补充。", "正文双栏宽度下所有文字可读。"),
        ],
    ),
    (
        "M1｜C2–LP11 中螺旋六态，45°/90°",
        "验证同一固定器件对四个实 LP 方位与 OAM±1 的输入方向无关操作。",
        "完整六态版放 Supplementary；正文可压缩成 Bloch 点、复矩阵和代表场图。",
        [
            Issue("P0", "ℓ=+1/−1 标签与模式方位阶数 ℓ 的符号混淆。", "改为 OAM_{+1}、OAM_{−1}。", "输入态名称唯一。"),
            Issue("P1", "OAM 两行只有环形强度，不能显示手性。", "补一个代表性 OAM 输入的相位图或相位绕行箭头。", "手性由复场证据确认。"),
            Issue("P1", "六态图尚未与共同相位参考下的 T 矩阵同图闭合。", "加入同一固定器件的 2×2 复矩阵、P_ret、指定 R_y 匹配度和轴角。", "六态输出均由同一 T 预测。"),
            Issue("P1", "45°/90° 未说明是 LP 物理旋转还是 Bloch 角。", "写 δ_LP=45°/90°；另给 η=2ℓδ。", "角度对 LP11 和后续 LP21 比较无歧义。"),
            Issue("P2", "六行场图与六行曲线过密。", "正文保留 0°、45°、OAM+ 三个代表态；全六态移补充。", "主文读者能快速抓住循环返回。"),
        ],
    ),
    (
        "M2｜C2–LP21 中螺旋六态，22.5°/45°",
        "验证 LP21 双重态的输入方向无关旋转与 OAM±2 行为。",
        "完整六态版放 Supplementary；与 M1 形成模式阶数对照。",
        [
            Issue("P0", "ℓ=+2/−2 容易被读作模式阶数而非 OAM 手性。", "改为 OAM_{+2}、OAM_{−2}。", "手性标签与 LP21 阶数分开。"),
            Issue("P1", "LP21 的物理方位周期和正交基底间隔未解释。", "caption 写 LP21 图样周期为 90°，a/b 物理方位相差 45°；22.5°为等幅实叠加。", "各输入角的物理意义可复算。"),
            Issue("P1", "45° 物理旋转对应 R_y(π)，90°对应 −I 的关系未在图中提示。", "正文解释物理角与 Bloch 角的 2ℓ 倍关系，避免将周期等价态当不同门。", "门命名与 SU(2) 拓扑一致。"),
            Issue("P1", "缺少复矩阵、轴纯度与共同相位参考。", "与 M1 相同，加入 T、P_ret、指定旋转匹配和 OAM 差分相位。", "六态图不再只是强度验证。"),
            Issue("P2", "与 M1 高度同构，占据主文空间过大。", "二者完整图均放补充；主文做一个紧凑的模式阶数比较表/图。", "正文避免重复展示相同结构。"),
        ],
    ),
    (
        "M3｜C4–LP21 主动操作与 LP11 spectator",
        "同一 C4 器件选择性操作 LP21，同时保持 LP11，是中螺旋最强的模式选择性证据。",
        "建议进入正文。",
        [
            Issue("P0", "右侧 LP11 仍写 Δθ=+45°，与输出保持矛盾。", "改为 same C4 device; LP11 spectator; target U_11≈I。", "图题与曲线结论一致。"),
            Issue("P1", "需要证明左右两列确实使用同一几何、长度、n_s、pitch 和端口。", "图注列出共享参数，并明确无重新优化。", "选择性结论基于同一固定器件。"),
            Issue("P1", "LP21 与 LP11 的复矩阵和选择性指标未集中报告。", "给出 T_21、T_11、P_ret、目标门匹配和 spectator 误差。", "选择性用复矩阵而非仅强度定义。"),
            Issue("P1", "OAM 手性仍缺相位图。", "增加一个 OAM±2 代表态相位快照。", "模式手性证据完整。"),
            Issue("P2", "左右列标题可更明确地表达 active/spectator。", "标题写 Active block: LP21；Spectator block: LP11。", "读图路径明确。"),
        ],
    ),
    (
        "F1｜C2 快螺旋多输入功率曲线",
        "展示 C2 对 LP11、LP21 在快区间的多模型功率演化。",
        "完整版放 Supplementary；正文只留代表输入。",
        [
            Issue("P1", "功率曲线非常拥挤，Model I 高频振荡掩盖主要物理。", "正文每模式只留 θ_in=0 与一个 OAM 输入；全输入角版本移补充。", "关键模型分叉一眼可见。"),
            Issue("P1", "场图无法单独说明累计角和相位。", "与 F2 的 unwrapped angle 共用 panel 或交叉引用。", "功率与旋转角证据互补。"),
            Issue("P1", "快照归一化方式和小圆轨迹未说明。", "caption 写逐帧/统一归一化、白圆与彩色圆含义。", "场图不被当作绝对功率图。"),
            Issue("P2", "BPM 与 Model III 颜色相近。", "BPM 改黑色；其余按统一色板。", "缩小后仍可区分。"),
        ],
    ),
    (
        "F2｜C2 快螺旋累计旋转",
        "最清楚地显示 C2–LP21 中 Model I 甚至预测错误旋转方向。",
        "建议作为快螺旋主文核心图。",
        [
            Issue("P0", "Accumulated rotation 未明确是连续展开的 LP 物理角，而非 Bloch 角或主值角。", "纵轴改为 unwrapped physical LP rotation δ_phys(z) (deg)，caption 给出与 η=2ℓδ 的关系。", "不同 ℓ 的曲线可正确比较。"),
            Issue("P1", "T1 与 II/III 符号相反的物理原因未在图中突出。", "增加简短注释：guided-mode channel reverses effective rotation；正文解释 LP02-like 通道。", "图本身能传达三层模型的必要性。"),
            Issue("P1", "四个输入角结果几乎重复。", "主文用均值粗线+输入角 spread 阴影；完整四行版本放补充。", "输入无关性与模型差异同时清楚。"),
            Issue("P2", "左右 panel 的纵轴范围和零线需更统一。", "加入明显零线并选择便于比较的刻度。", "正负方向切换更醒目。"),
        ],
    ),
    (
        "F3｜C2 快螺旋出口角–n_circle",
        "展示可调范围与输入方位不敏感性。",
        "建议与 F6 合并为统一 2×2 可调性图。",
        [
            Issue("P0", "纵轴仍需说明是 unwrapped physical LP rotation。", "标题/纵轴统一写 δ_exit^unwrap (deg)。", "不与 Bloch 角混淆。"),
            Issue("P1", "四个输入方向各占一行但信息重复。", "对每个 n_s 画四输入平均值和 min–max 阴影；必要时另附最大输入依赖误差。", "图面更紧凑且直接量化输入无关性。"),
            Issue("P1", "横坐标 n_circle 从高到低，视觉上“控制量增加”方向相反。", "主横轴改 ε=(n_c²−n_s²)/(n_c²−n_cl²)，顶部给 n_s 次坐标。", "可直接比较 R_z~ε 与 R_y~ε²。"),
            Issue("P1", "filled/native 与 open/coherent reconstruction 说明不够直观。", "将 native BPM 与 coherent reconstruction 分开图例，解释二者数据来源和适用点。", "marker 含义无需正文猜测。"),
            Issue("P2", "BPM 与 III 颜色接近。", "统一改黑色 BPM。", "图例清晰。"),
        ],
    ),
    (
        "F4｜C4 快螺旋多输入功率曲线",
        "展示 C4 对 LP11 与 LP21 的不同动态响应。",
        "完整版放 Supplementary；正文由 F5/F6 承担主结论。",
        [
            Issue("P1", "曲线密度过高，C4–LP21 多周期振荡难以追踪。", "正文只留一个代表输入和一个 OAM 输入；完整四输入移补充。", "主结论不被局部振荡淹没。"),
            Issue("P1", "C4–LP11 的显著 Model I 偏差需要与“直接分裂为零”并列解释。", "caption 强调 symmetry-forbidden direct splitting does not imply dynamic transparency。", "读者不会把高阶响应误认为数值噪声。"),
            Issue("P1", "快照强度不能验证 OAM 手性。", "代表性 OAM case 增加相位图/手性量。", "复态证据完整。"),
            Issue("P2", "场图和曲线重复度高。", "压缩行数，统一共享轴与图例。", "双栏可读。"),
        ],
    ),
    (
        "F5｜C4 快螺旋累计旋转",
        "显示 C4–LP11 中外部模式将 Model I 的约 230° 修正到接近 BPM/II/III 的约 320°，并给出 LP21 对照。",
        "建议进入正文。",
        [
            Issue("P0", "累计角定义需与 F2 完全相同。", "统一为 δ_phys^unwrap(z)，注明正方向和观察方向。", "F2/F5 可直接横向比较。"),
            Issue("P1", "C4–LP11 的非零快旋转与零直段分裂之间的关系未在图中提示。", "增加注释：direct Δβ=0, but multimode/Floquet response ≠0。", "对称选择规则的适用边界明确。"),
            Issue("P1", "四输入行重复。", "主文压缩为均值+spread；完整版本入补充。", "突出模型差异和输入无关性。"),
            Issue("P2", "T1/II/III 名称和色板需统一。", "按全局规范修改。", "与其他图一致。"),
        ],
    ),
    (
        "F6｜C4 快螺旋出口角–n_circle",
        "展示 C4–LP11/LP21 的可调角和模型差异。",
        "与 F3 合并为统一快螺旋可调性图。",
        [
            Issue("P0", "出口角符号/定义需与 D1、F2、F5 共用同一传播相位约定。", "在源数据层统一 sign convention 后重画。", "所有角度图的正负号可由同一复矩阵定义导出。"),
            Issue("P1", "C4–LP11 中 Model I 系统性偏低是关键结果，但目前被四行重复稀释。", "改为单 panel 均值曲线+spread，直接标出最大模型差。", "关键增量一眼可见。"),
            Issue("P1", "横轴建议改 ε，并给 n_s 次坐标。", "与 F3 统一。", "弱扰动标度直接可见。"),
            Issue("P2", "可与 F3 共用 2×2 布局，减少两张大图。", "四 panel：C2–LP11、C2–LP21、C4–LP11、C4–LP21。", "正文图数减少且信息更集中。"),
        ],
    ),
    (
        "D1｜直段 R_z 相位–小圆折射率",
        "展示 C2 同时作用于 LP11/LP21，而 C4 选择性作用于 LP21。",
        "必须修正符号后进入正文。",
        [
            Issue("P0", "标题 θ_z=φ_b−φ_a 与此前保存结果呈现完全相反的符号。", "使用原始 t_a,t_b 重新计算 θ_z=unwrap arg(t_b t_a*)；核对 a/b 标签、e^{±iβz} 和 BPM 相位导出。", "n_s=1.444 的端点符号与复矩阵、OAM 相位和门定义一致。"),
            Issue("P0", "图中未写 L_z、ρ、λ，无法复现斜率和总相位。", "明确写 L_z=10 mm、ρ=4.2 μm、λ=1.55 μm、d_s 和端口定义。", "读者可由 ΔβL 复算曲线。"),
            Issue("P0", "相位展开和共同相位参考未说明。", "caption 写 continuous unwrapping、φ_b−φ_a、两次输入共享相位参考。", "不存在独立去全局相位后拼矩阵的做法。"),
            Issue("P1", "C4–LP11 零曲线 panel 看似空白。", "加 inset 或标注最大 |θ_z| 与数值容差。", "“零”成为量化结论而非视觉空白。"),
            Issue("P1", "三模型几乎重合时无法看出差异。", "主 panel 保留三模型；补一个 θ_II−θ_I、θ_III−θ_I 的小 inset 或补充图。", "读者能判断重合是物理结果而非漏画。"),
            Issue("P2", "横轴可改为 ε，并保留 n_s 次坐标。", "用于与快螺旋二阶响应直接比较。", "R_z~ε 的一阶标度更清楚。"),
        ],
    ),
    (
        "D2｜C2 直段：a、b 与 OAM± 的传播",
        "直观展示 LP 基底 R_z 等价于 OAM 基底 R_x；C2 对 ℓ=1、2 都作用。",
        "可放 Supplementary；正文提取一组代表 OAM 手性交换。",
        [
            Issue("P0", "未说明 a/b 是扰动直段本征模还是无扰动圆芯标准 LP 模。", "在图题和 caption 明写 input/monitor basis，并说明是否使用渐变接入。", "纯 a/b 恒定功率的物理含义明确。"),
            Issue("P0", "未写 n_s 与 L_z，振荡周期不可复现。", "补全 n_s、L_z、ρ、λ、d_s。", "由 Δβ 可重建周期。"),
            Issue("P0", "OAM 环形强度不能区分 ± 手性。", "至少给一组 OAM+→OAM− 的相位快照。", "手性翻转有复场证据。"),
            Issue("P1", "若采用标准端口，需要报告外模/LP02 功率；若采用本征端口，需要说明这是理想内部基底。", "根据实际数据选择明确口径，不把两种输入定义混在同一结论中。", "起点功率与总功率口径自洽。"),
            Issue("P1", "功率曲线未明确 P/P_in 或 conditional。", "统一纵轴和归一化说明。", "起点和峰值可正确解释。"),
            Issue("P2", "LP a/b 两行基本为常数，可进一步压缩。", "正文只用公式/小 inset 表示 a、b 不变，把版面留给 OAM 交换。", "信息密度更合理。"),
        ],
    ),
    (
        "D3｜C4 直段：LP11 spectator 与 LP21 OAM 交换",
        "直段选择性最直观的动力学证据：LP11 近恒等，LP21 获得可调 R_z。",
        "建议进入正文，前提是明确输入基底与参数。",
        [
            Issue("P0", "与 D2 相同，输入/监测基底未说明。", "明确 perturbed eigenmodes 或 unperturbed circular-core ports；若有 taper 一并说明。", "spectator 与主动块的结论可复现。"),
            Issue("P0", "缺 n_s、L_z，无法解释约五个 OAM 振荡周期。", "在标题或 caption 给完整参数。", "振荡周期与 D1 的相位斜率一致。"),
            Issue("P0", "OAM±2 强度快照不显示手性。", "补相位快照或 OAM Stokes；强度图可保留形状。", "正负手性不依赖标签猜测。"),
            Issue("P1", "应证明 LP11 与 LP21 使用同一个 C4 器件和同一 n_s。", "共享参数集中列出，不允许分别调参。", "模式选择性结论成立于同一器件。"),
            Issue("P1", "应把 D1 的 R_z 角与 D3 的 OAM 周期作定量闭环。", "标注 L_π=π/|Δβ|、L_osc=2π/|Δβ|，并与曲线峰位置比较。", "相位标定与动力学图相互验证。"),
            Issue("P2", "左侧 LP11 四行几乎完全平坦。", "正文压缩成一个 spectator block 指标；完整四行放补充。", "正文更聚焦 LP21 选择性。"),
        ],
    ),
]


def collect_counts() -> dict[str, int]:
    counts = {"P0": 0, "P1": 0, "P2": 0}
    for issue in GLOBAL_ISSUES:
        counts[issue.priority] += 1
    for _, _, _, issues in FIGURES:
        for issue in issues:
            counts[issue.priority] += 1
    return counts


def build_story() -> list:
    story: list = []
    counts = collect_counts()
    total = sum(counts.values())

    story += [
        Spacer(1, 15*mm),
        P("螺旋 LP/OAM 论文图件问题总清单", "TitleCN"),
        P("逐图修改建议、优先级与验收标准", "SubtitleCN"),
        P(
            "覆盖范围：本轮对话中实际可见的两张结构示意图，以及 S2、M1–M3、F1–F6、D1–D3。"
            "若原始“14 Figures”包中另有未单独展示的 S1，则该图不在本清单的逐图结论范围内。",
            "SubtitleCN",
        ),
        Spacer(1, 4*mm),
        P(
            "总体判断：科学结果已经很强，当前主要风险不是缺少曲线，而是符号、端口基底、归一化和复相位定义尚未完全统一。"
            "这些问题若不先修正，会直接影响 R_z/R_y 门角、OAM 手性、Z–Y–Z 级联和多模式选择性的可信度。",
            "CalloutCN",
        ),
    ]
    stats = [
        [P("清单总项数", "TableHeaderCN"), P("P0 必须修正", "TableHeaderCN"), P("P1 证据补齐", "TableHeaderCN"), P("P2 排版优化", "TableHeaderCN")],
        [P(str(total), "H1CN"), P(str(counts["P0"]), "H1CN"), P(str(counts["P1"]), "H1CN"), P(str(counts["P2"]), "H1CN")],
    ]
    stat_table = Table(stats, colWidths=[65*mm]*4)
    stat_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("BACKGROUND", (0, 1), (0, 1), LIGHT),
        ("BACKGROUND", (1, 1), (1, 1), PRIORITY_COLOR["P0"]),
        ("BACKGROUND", (2, 1), (2, 1), PRIORITY_COLOR["P1"]),
        ("BACKGROUND", (3, 1), (3, 1), PRIORITY_COLOR["P2"]),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [stat_table, Spacer(1, 8*mm)]
    story += [
        P("使用方法", "H2CN"),
        P("先关闭全部 P0，再处理 P1；P2 可在科学定义锁定后统一重绘。每一项右侧方框用于修改完成后的人工勾选。"),
        P("建议每次重绘同时保存：源数据、绘图脚本、完整参数、端口定义、相位规范、原图和修改后图。"),
        PageBreak(),
    ]

    story += [P("1. 投稿前阻断项：最先关闭的 12 项", "H1CN")]
    top_p0 = [x for x in GLOBAL_ISSUES if x.priority == "P0"][:10]
    top_p0 += [
        next(i for name, _, _, arr in FIGURES if name.startswith("D1") for i in arr if "符号" in i.problem),
        next(i for name, _, _, arr in FIGURES if name.startswith("结构图 B") for i in arr if "直结构" in i.problem),
    ]
    story += [issue_table(top_p0), PageBreak()]

    story += [P("2. 全部图共用的定义与排版规范", "H1CN")]
    story += [P("建议在重绘任何单图之前先锁定本节；否则会反复返工。", "CalloutCN")]
    story += [P("推荐统一符号", "H2CN")]
    story += [P(
        "Θ(z)：结构机械方位；K_h=dΘ/dz；Λ_h=2π/|K_h|；Λ_pattern=Λ_h/N；δ：LP 图样物理旋转；"
        "η=2ℓδ：LP 基底 R_y 的 Bloch 角；ζ=φ_b−φ_a：LP 基底 R_z 角；N_turn：完整机械圈数。",
        "EquationCN",
    )]
    story += [issue_table(GLOBAL_ISSUES), PageBreak()]

    story += [P("3. 图件总定位与主文/补充材料建议", "H1CN")]
    placement_rows = [
        ("结构图 A+B", "正文 Figure 1", "定义 C_N 几何、四工作区和 Z–Y–Z 总架构。", "符号冲突、周期定义、直段功能不突出。"),
        ("S2", "补充；正文抽取", "慢螺旋、spectator 和 ER 光谱。", "ER 口径、60 dB floor、信息过密。"),
        ("M1/M2", "补充", "两个模式的完整六态验证。", "缺复矩阵与 OAM 相位，主文重复度高。"),
        ("M3", "正文", "同一 C4 器件：LP21 active、LP11 spectator。", "Δθ 标签错误，需同器件复矩阵。"),
        ("F1/F4", "补充", "快螺旋完整多输入功率演化。", "曲线过密。"),
        ("F2/F5", "正文", "累计角揭示三模型差异和 Model I 失效。", "累计角定义与符号必须统一。"),
        ("F3/F6", "合并后正文", "可调性、输入方位不敏感和模式/对称性依赖。", "重复四行、横轴方向、marker 说明。"),
        ("D1", "正文", "直段 R_z 可调与 C_N 选择规则。", "相位符号必须先修正。"),
        ("D2", "补充/正文简版", "C2 对 ℓ=1,2 均作用；R_z↔OAM R_x。", "输入基底、n_s、L_z 未说明。"),
        ("D3", "正文", "C4 选择性：LP11 spectator、LP21 OAM 交换。", "输入基底、参数和 OAM 相位证据。"),
    ]
    story += [summary_table(placement_rows), PageBreak()]

    section_no = 4
    for name, purpose, placement, issues in FIGURES:
        story += [P(f"{section_no}. {name}", "H1CN")]
        story += [P(f"<b>图的任务：</b>{purpose}")]
        story += [P(f"<b>建议定位：</b>{placement}")]
        story += [issue_table(issues)]
        story += [Spacer(1, 3*mm)]
        story += [P("重绘前确认", "H2CN")]
        story += [P("□ 源数据与当前图一一对应　　□ 参数表已冻结　　□ 端口/基底已写入 caption　　□ 相位与归一化规范已锁定", "SmallCN")]
        story += [PageBreak()]
        section_no += 1

    story += [P(f"{section_no}. 推荐的最终正文图序列", "H1CN")]
    final_rows = [
        ("Figure 1", "统一结构与机制", "通用 C_N 几何 + Slow/Middle/Fast/Straight + Z_L–Y–Z_R 架构。", "先锁定 Θ、K_h、Λ_h、N_turn、δ、η、ζ。"),
        ("Figure 2", "慢螺旋", "从 S2 抽取 C2–LP11、C4–LP21、LP11 spectator 与一个 ER 带宽总结。", "ER 定义、floor、截止与材料色散边界。"),
        ("Figure 3", "中螺旋选择性门", "以 M3 为主体；加入 LP21/LP11 复矩阵、保留率和指定门匹配。", "同一固定器件、共同相位参考。"),
        ("Figure 4", "快螺旋三层模型", "合并 F2/F5 的四个 case，突出 Model I 错符号和外模修正。", "unwrapped physical angle。"),
        ("Figure 5", "快螺旋可调性", "合并 F3/F6；均值+输入方向 spread；ε 主轴、n_s 次轴。", "指定 R_y 角、轴纯度、P_ret。"),
        ("Figure 6", "直段 R_z", "D1 修正版 + D3 选择性 OAM 交换 + 一个相位/Bloch 示意。", "D1 相位符号、输入基底、n_s/L_z。"),
        ("Figure 7", "多模式独立 SU(2)", "C2/C4 的 Z–Y–Z 三层网络，在 LP11 和 LP21 上实现两个不同目标矩阵。", "完整复矩阵级联、响应矩阵满秩、跨块共同相位边界。"),
    ]
    story += [summary_table(final_rows), Spacer(1, 6*mm)]
    story += [P(
        "论文最终结论建议限定为：symmetry-selective, blockwise programmable SU(2) transformations over a predefined finite set of modal doublets。",
        "CalloutCN",
    )]
    story += [PageBreak()]

    section_no += 1
    story += [P(f"{section_no}. 每张图 caption 的最低信息要求", "H1CN")]
    caption_items = [
        Issue("P0", "器件参数", "写明 N、ρ、d_s、n_s、λ、L、K_h/Λ_h、N_turn，以及首个小圆方位。", "第三方无需查代码即可重建 case。"),
        Issue("P0", "输入与监测", "写明标准圆芯端口/扰动本征模/RSoft 锚定端口；写明 a/b/OAM 定义。", "输入和输出投影空间唯一。"),
        Issue("P0", "相位规范", "写明传播约定、φ_b−φ_a 或 φ_a−φ_b、正旋转观察方向、连续展开方法。", "所有角度图符号一致。"),
        Issue("P0", "归一化", "写明 absolute/conditional；场快照逐帧还是全局归一化；功率是否以原始输入为 1。", "起点、峰值与泄漏可正确解释。"),
        Issue("P1", "模型定义", "Model I=P；II=P⊕D；III=P⊕D⊕C_R；箱体 R_max、谱窗和边界条件。", "“精确”不会被误写成开放边界全矢量精确。"),
        Issue("P1", "指标定义", "ER、P_ret、F_target、轴倾斜、最坏输入保留率均写公式或指向 Methods。", "指标名称与数学量一致。"),
        Issue("P2", "场图符号", "解释白色纤芯边界、彩色扰动圆、虚线方向、相位色标。", "图形元素无未定义含义。"),
    ]
    story += [issue_table(caption_items), PageBreak()]

    section_no += 1
    story += [P(f"{section_no}. 最终验收清单", "H1CN")]
    signoff = [
        ("科学定义", "□ D1 符号已核对　□ 所有角度符号统一　□ N/N_turn/Λ_h/Λ_pattern 无冲突"),
        ("端口与相位", "□ input/monitor basis 明确　□ 两次基底输入共享相位参考　□ OAM 有复相位证据"),
        ("归一化", "□ absolute/conditional 不混用　□ 场快照标明归一化　□ 起点投影误差不当作损耗"),
        ("三模型", "□ Model I/II/III 命名统一　□ 同参数比较　□ Model III 箱体/谱窗收敛边界明确"),
        ("慢螺旋", "□ branch-aligned 限定　□ ER 公式/floor/门限/截止明确　□ spectator 标签正确"),
        ("中螺旋", "□ cyclic-return 条件　□ 同一固定器件六态　□ 复矩阵/指定门指标闭合"),
        ("快螺旋", "□ unwrapped physical angle　□ R_y 轴纯度　□ 可调范围+输入 spread　□ 禁戒高阶响应说明"),
        ("直段", "□ ζ=φ_b−φ_a 符号锁定　□ n_s/L_z/ρ/λ 完整　□ D1 与 OAM 周期定量一致"),
        ("排版", "□ BPM 黑色　□ 双栏打印可读　□ 共享纵轴标题　□ 主文与补充材料已拆分"),
        ("最终架构", "□ 两模式不同 SU(2) 示例　□ 响应矩阵满秩/条件数　□ 跨模式共同相位边界说明"),
    ]
    data = [[P("验收类别", "TableHeaderCN"), P("完成条件", "TableHeaderCN"), P("签字/日期", "TableHeaderCN")]]
    for cat, condition in signoff:
        data.append([P(cat, "TableCN"), P(condition, "TableCN"), P("", "TableCN")])
    table = Table(data, colWidths=[42*mm, 185*mm, 38*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("GRID", (0, 0), (-1, -1), 0.45, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFB")]),
    ]))
    story += [table, Spacer(1, 6*mm)]
    story += [P(
        "建议关闭顺序：D1 相位符号 → 全局符号/周期/端口规范 → 结构图 → D2/D3 → M3 复矩阵 → F2/F5 定义 → F3/F6 合并 → S2 ER → 主文压缩与最终 Z–Y–Z 演示。",
        "EquationCN",
    )]
    story += [P("文档结束。", "SubtitleCN")]
    return story


def main() -> None:
    doc = ReviewDocTemplate(str(OUTPUT))
    doc.build(build_story())
    print(OUTPUT)


if __name__ == "__main__":
    main()
