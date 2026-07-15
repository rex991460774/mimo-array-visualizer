"""Structured, localized user-manual content for the desktop application.

The manual is intentionally task oriented.  It explains what a control is for,
how to use it, what result to expect, and what to check when the result differs
from expectations.  Mathematical background belongs in engineering documents,
not in this in-app guide.
"""

from __future__ import annotations

from dataclasses import dataclass
import html


@dataclass(frozen=True, slots=True)
class ManualSection:
    """One scannable section within a manual chapter."""

    heading: str
    paragraphs: tuple[str, ...] = ()
    steps: tuple[str, ...] = ()
    bullets: tuple[str, ...] = ()
    note: str | None = None
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class ManualChapter:
    """A stable manual chapter that can be shown in navigation and search."""

    key: str
    title: str
    summary: str
    sections: tuple[ManualSection, ...]


MANUAL_CHAPTER_IDS = (
    "quick_start",
    "workspace",
    "layout_editing",
    "virtual_overview",
    "global_controls",
    "dbf_1d",
    "dbf_2d",
    "dbf_dictionary",
    "channel_patterns",
    "files_reports",
    "shortcuts_state",
    "troubleshooting",
)

_SUPPORTED_LANGUAGES = frozenset({"zh", "en", "ja"})


def _zh_chapters() -> tuple[ManualChapter, ...]:
    return (
        ManualChapter(
            "quick_start",
            "快速开始",
            "从空白布局到完成一次可复现检查的最短操作流程。第一次使用时，按本章顺序操作即可。",
            (
                ManualSection(
                    "开始前确认",
                    paragraphs=(
                        "程序启动后会恢复上次关闭时的阵列、频率、显示方式、活动页签和窗口布局。先看顶部状态标签，确认当前频率、DBF 字典和通道幅相状态是否符合本次任务。",
                    ),
                    bullets=(
                        "如果要从头开始，在“物理与虚拟阵列”页点击“清空”，布局会回到 1T1R 起始状态。",
                        "如果已有阵面文件，使用“文件 > 导入阵面JSON”；该操作只读取 TX/RX 坐标。",
                        "如果没有现成布局，可在底部输入 T、R 数量并点击“应用阵列”。T 和 R 都允许 1 到 16。",
                    ),
                    note="状态栏会持续显示最近一次操作的结果。遇到没有明显变化的情况，先读状态栏。",
                ),
                ManualSection(
                    "完成一次基础检查",
                    steps=(
                        "在物理阵列中添加、拖动或自动生成 TX/RX，确认通道名称和位置正确。坐标在界面中统一按 λ 显示。",
                        "在底部输入工作频率并按 Enter，或将焦点移出输入框；再设置竞争峰裕量。",
                        "查看虚拟阵列中的唯一点、重复点和 TX/RX 组合提示，再查看右侧总览中的通道数、口径和分辨率。",
                        "切换到“1D DBF”，分别检查方位和俯仰。拖动真实角标线，或点击播放观察峰值是否连续跟随。",
                        "当方位和俯仰都具备有效孔径时，切换到“2D DBF”，拖动十字线检查关注角度。",
                        "使用“文件 > 导出阵面JSON”保存坐标；需要交付结果时，再输出当前配置性能报告。",
                    ),
                ),
                ManualSection(
                    "结果应该是什么样",
                    bullets=(
                        "有效方向会显示曲线、真实角、估计峰值和测角指标。",
                        "没有有效孔径的方向会显示中性能力提示，而不是平直曲线或伪热图。",
                        "重复虚拟点、边界限制或竞争峰不足会在图表、总览或状态提示中明确标出。",
                    ),
                    warning="不要只看一张静态图就保存结论。至少拖动或播放一遍关注角度范围，并确认当前使用的字典和通道幅相状态。",
                ),
            ),
        ),
        ManualChapter(
            "workspace",
            "主窗口与三页工作区",
            "认识主窗口各区域，知道每一页适合完成什么任务，以及哪些信息会随布局变化自动刷新。",
            (
                ManualSection(
                    "窗口区域",
                    bullets=(
                        "菜单栏：导入导出、撤销重做、通道幅相、DBF 字典、语言和帮助。",
                        "顶部标题区：只显示频率、当前 DBF 字典和通道幅相三个全局状态。",
                        "主页签：物理与虚拟阵列、1D DBF、2D DBF。可用鼠标或 Ctrl+1、Ctrl+2、Ctrl+3 切换。",
                        "右侧总览：显示阵列规模、虚拟通道利用、口径、分辨率和测角评估。",
                        "底部命令栏：频率、竞争峰裕量、自动排阵和 DBF 显示方式。",
                        "状态栏：显示导入、拖动、播放、错误恢复和报告生成等最近操作。",
                    ),
                ),
                ManualSection(
                    "三页分别做什么",
                    bullets=(
                        "物理与虚拟阵列：编辑真实 TX/RX 位置，对照虚拟点，并读取总览指标。",
                        "1D DBF：单独检查方位或俯仰；即使只有一个方向有效，仍可继续使用有效的一侧。",
                        "2D DBF：同时检查方位和俯仰；只有两个方向都有有效孔径时才显示热图和播放控件。",
                    ),
                    note="如果 2D 页提示能力不足，但 1D 的某一方向可用，请直接转到 1D 页，不需要为了显示 2D 图而修改本来正确的单轴阵列。",
                ),
                ManualSection(
                    "调整窗口",
                    steps=(
                        "拖动主区域与右侧总览之间的分隔条，给图表或指标留出更多空间。",
                        "调整窗口大小时，等待短暂刷新结束再读取图表；程序会对连续缩放进行防抖处理。",
                        "长文件名或被省略的状态文本可悬停查看完整 tooltip。",
                    ),
                    bullets=(
                        "窗口最小尺寸为 1100×650；较小屏幕上应优先收窄总览侧栏。",
                        "窗口位置和分隔条比例会在正常关闭时保存，下次启动自动恢复并限制在当前屏幕工作区内。",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "layout_editing",
            "编辑 TX/RX 阵列",
            "添加、选择、拖动、键盘微调、删除和自动排阵。所有坐标都按 λ 展示，布局变化后相关视图自动更新。",
            (
                ManualSection(
                    "添加与自动排阵",
                    steps=(
                        "点击“+TX”或“+RX”添加一个通道。新通道会放在同类通道右侧的空闲网格位置并自动选中。",
                        "需要一次建立完整阵列时，在底部“自动排阵”中分别输入 T 和 R 数量。",
                        "点击“应用阵列”或在数量输入框中按 Enter。程序会替换当前布局并立即刷新。",
                    ),
                    bullets=(
                        "TX 数量范围为 1～16，RX 数量范围为 1～16。",
                        "添加、自动排阵、清空、导入、拖动和键盘移动都可撤销。",
                        "“清空”并非生成零通道，而是恢复为可用的 1T1R 起始布局。",
                    ),
                    warning="“应用阵列”和“清空”会替换当前坐标。需要保留当前布局时，先导出阵面 JSON。",
                ),
                ManualSection(
                    "选择、拖动与精确移动",
                    steps=(
                        "在物理阵列图中单击 TX 或 RX 将其选中。",
                        "按住鼠标左键拖动；接近边缘时绘图区会扩展。松开后位置吸附到 0.5λ 显示网格，并重新计算全部结果。",
                        "选中通道后按方向键，每次沿显示网格移动 0.5λ。输入框获得焦点时，方向键仍用于编辑输入，不会移动阵元。",
                        "拖动尚未结束时按 Esc，可恢复拖动前的位置；未拖动时按 Esc 会取消选择或退出删除模式。",
                    ),
                    note="通道移动后会按位置重新整理同类通道编号。依赖 Tx1、Rx1 等名称的外部文件应在布局最终确定后再导入。",
                ),
                ManualSection(
                    "删除与历史",
                    steps=(
                        "选中通道后按 Delete，可直接删除当前通道。",
                        "没有选中通道时，点击“删除”或按 Delete 会进入持续删除模式；随后直接点击多个通道。",
                        "再次点击“删除”或按 Esc 退出删除模式。",
                        "使用“编辑 > 撤销阵列编辑”和“重做阵列编辑”恢复最近操作。",
                    ),
                    bullets=(
                        "每一类至少保留 1 个通道，因此最后一个 TX 或最后一个 RX 不能删除。",
                        "历史最多保存 50 步，只覆盖阵列布局编辑，不覆盖频率、字典或通道幅相。",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "virtual_overview",
            "虚拟阵列与总览指标",
            "用虚拟点和右侧总览快速确认阵列是否按预期组合、是否存在重复点，以及哪些方向具备有效能力。",
            (
                ManualSection(
                    "查看虚拟阵列",
                    steps=(
                        "完成物理阵列编辑后，查看右侧虚拟阵列图；每个点来自一组 TX/RX 组合。",
                        "将鼠标悬停在虚拟点附近，读取该点对应的通道组合和坐标。",
                        "对照唯一虚拟点数与总虚拟通道数；两者不一致时，说明存在重合点。",
                    ),
                    bullets=(
                        "TX、RX 和虚拟阵列坐标均按 λ 显示，右侧口径同时换算为 mm。",
                        "重复点不会被静默忽略，利用率和重复提示会反映它们。",
                    ),
                ),
                ManualSection(
                    "读取阵列总览",
                    bullets=(
                        "通道数：当前 T×R 规模。",
                        "虚拟通道：唯一点/全部组合，以及对应利用率。",
                        "方位/俯仰口径：当前方向上的有效展开，按工作频率换算为 mm。",
                        "方位/俯仰分辨率：用于比较不同布局；显示不可用时表示该方向没有有效展开。",
                        "能力提示：只有一个方向有效时保留该方向的 1D 结果；两个方向都有效时才开放 2D。",
                    ),
                    note="频率变化会改变 mm 换算，但不会改变图中按 λ 表示的坐标。比较两个布局时，请确认频率一致。",
                ),
                ManualSection(
                    "读取测角评估",
                    bullets=(
                        "不折叠范围：当前设置下可连续使用的真实角区间。",
                        "范围内误差：在显示范围内观察最大误差是否满足任务要求。",
                        "竞争峰裕量：与底部设置的判据一起判断峰值是否足够明确。",
                        "截断原因：说明范围为何在某一侧停止，例如到达数据边界、阵列边界或谱可靠性不足。",
                    ),
                    warning="总览是当前字典、通道幅相、频率和布局共同作用下的结果。更换其中任何一项后，都应重新核对总览。",
                ),
            ),
        ),
        ManualChapter(
            "global_controls",
            "全局参数与显示",
            "底部命令栏中的设置会影响尺寸换算、可靠性判断、布局和图表显示。",
            (
                ManualSection(
                    "频率",
                    steps=(
                        "点击频率输入框，输入正数；可直接输入数字，也可带 GHz 或 G 后缀。",
                        "按 Enter 或将焦点移出输入框以应用。",
                        "查看顶部频率标签和右侧 mm 口径，确认新值已经生效。",
                    ),
                    note="输入为空、非数字、零或负数时，程序会恢复最近一次有效频率，并在状态栏说明。",
                ),
                ManualSection(
                    "竞争峰裕量",
                    steps=(
                        "输入不小于 0 的 dB 数值。",
                        "按 Enter 或移出焦点应用，随后查看测角评估中的裕量和截断原因。",
                    ),
                    paragraphs=(
                        "该值是操作判据：设得更严格时，可用角区可能缩小；设得更宽松时，需要人工更谨慎地检查相邻竞争峰。",
                    ),
                    warning="不要为了扩大可用范围而随意降低裕量。应使用项目验收要求或团队约定的值。",
                ),
                ManualSection(
                    "自动排阵与 DBF 显示",
                    bullets=(
                        "自动排阵：输入 1–16 的 T/R 数量并应用，快速得到一个可继续拖动修改的起始布局。默认沿水平方向排列，通常先形成方位孔径；要使用俯仰或 2D DBF，需再将部分通道沿 y 方向拉开。",
                        "dB：适合查看低电平区域、旁瓣和竞争峰。",
                        "模值：适合快速观察主峰轮廓和热图边界。",
                        "切换 dB/模值只改变显示标尺，不改变当前布局、字典或真实角。",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "dbf_1d",
            "1D DBF：方位与俯仰",
            "分别检查方位和俯仰角谱，使用拖动、播放、暂停和停止确认峰值在关注范围内连续跟随。",
            (
                ManualSection(
                    "开始检查",
                    steps=(
                        "切换到“1D DBF”。左侧为方位，右侧为俯仰。",
                        "确认图中的真实角标线、估计峰值标记、当前帧和角度文字可见。",
                        "将鼠标悬停在曲线上读取角度和显示值。",
                        "靠近真实角标线后按住左键拖动，松开时停在新的真实角。",
                    ),
                    bullets=(
                        "一个方向没有孔径时，该侧显示能力提示并禁用播放；另一侧若有效，仍可正常使用。",
                        "拖动真实角会暂停当前扫描，并立即更新该方向的曲线和指标。",
                    ),
                ),
                ManualSection(
                    "播放、暂停与停止",
                    steps=(
                        "点击“播放”，真实角会从 -90° 扫描到 +90°。",
                        "播放过程中再次点击同一按钮可暂停；按钮和状态栏会显示暂停位置。",
                        "暂停后再次点击可继续。点击“停止”会结束当前方向的扫描。",
                        "切换到另一个方向播放时，当前扫描状态会按界面提示更新。",
                    ),
                    note="播放用于发现跳变或竞争峰，拖动用于复查具体角度。建议先播放，再对异常区间逐点拖动。",
                ),
                ManualSection(
                    "判断结果",
                    bullets=(
                        "估计峰值应在关注范围内稳定跟随真实角，不应突然跳到远处。",
                        "查看峰值与真实角的偏差，同时查看竞争峰裕量和截断原因。",
                        "在 dB 显示下检查是否出现接近主峰的竞争峰；在模值显示下复核主峰轮廓。",
                    ),
                    warning="如果曲线与预期方向相反，先确认当前 DBF 字典是否选错了“理想反向相位”或导入字典的相位反向选项，不要先修改阵列坐标。",
                ),
            ),
        ),
        ManualChapter(
            "dbf_2d",
            "2D DBF 热图",
            "在方位和俯仰都有效时，同时查看两个方向，并用独立播放或拖动十字线检查二维关注区域。",
            (
                ManualSection(
                    "使用条件与图中标记",
                    bullets=(
                        "只有方位和俯仰都具备有效孔径时，2D 热图才可用。",
                        "白色十字线表示当前真实方位和真实俯仰，峰值标记表示当前估计位置。",
                        "颜色条随 dB/模值切换同步变化；顶部轻量徽标显示当前角度或峰值信息。",
                    ),
                    note="若页面显示能力提示，先回到物理页增加相应方向的阵列展开；如果设计本来就是单轴阵列，应改用 1D DBF。",
                ),
                ManualSection(
                    "播放和拖动",
                    steps=(
                        "点击“播放方位”只改变真实方位，点击“播放俯仰”只改变真实俯仰。",
                        "两个按钮可以同时开启，使两个方向同时循环。再次点击某个按钮只暂停对应方向。",
                        "点击“停止”会同时结束两个方向的播放。",
                        "将鼠标移到十字线附近，按住左键拖动，可同时设置两个真实角；拖动会停止自动播放。",
                        "悬停热图读取当前位置的方位、俯仰和显示值。",
                    ),
                ),
                ManualSection(
                    "二维复查建议",
                    bullets=(
                        "先分别播放方位和俯仰，确认单轴变化没有异常，再同时播放。",
                        "将十字线拖到项目关注区域的中心、边缘和四角，记录峰值是否仍靠近真实角。",
                        "出现多个相近亮区时，切到 dB 显示并结合 1D 页逐轴定位问题。",
                    ),
                    warning="2D 热图适合定位问题，不应代替性能报告中的范围统计。需要交付或批量比较时请输出报告。",
                ),
            ),
        ),
        ManualChapter(
            "dbf_dictionary",
            "配置 DBF 字典",
            "选择测角使用的四种字典，预览方位或俯仰矩阵，并在导入外部数据时明确物理/虚拟通道目标。",
            (
                ManualSection(
                    "四种模式",
                    bullets=(
                        "理想几何字典：默认模式，适合先检查阵列布局和基本交互。",
                        "理想反向相位字典：用于快速核对外部数据或系统的方向约定。",
                        "通道幅相校准字典：使用“配置通道幅相”中当前已导入的数据；未配置的通道保持理想。",
                        "导入 CSV/XLSX 字典：使用外部仿真、标定或实测表格，可分别加载方位和俯仰。",
                    ),
                    note="选择单选项只更新预览；必须点击“应用字典”，主窗口才切换到该模式。关闭弹窗不会应用尚未确认的模式。",
                ),
                ManualSection(
                    "导入外部字典",
                    steps=(
                        "先选择导入目标：“物理通道”对应 Tx1、Tx2、Rx1…；“虚拟通道”对应 Tx1Rx1、Tx1Rx2…的顺序。",
                        "点击“加载方位字典”或“加载俯仰字典”，选择 CSV、TSV、XLSX 或 XLSM。",
                        "切换方位/俯仰预览，核对角度行数、通道列数、文件名和目标类型。",
                        "按需要勾选“导入字典相位反向”或“按 0° 相位校准”，并再次查看预览。",
                        "至少加载一个方向后选择“导入 CSV/XLSX 字典”，点击“应用字典”。",
                    ),
                    bullets=(
                        "表格需要表头、角度列和通道数据列；优先使用与当前通道一致的列名。",
                        "普通实数数据按相位角读取；包含复数格式的数据按复数响应读取。",
                        "可以只加载一个方向；未加载的方向继续使用默认数据。",
                    ),
                    warning="导入前先固定阵列通道数量和编号。之后改变 T/R 数量可能使外部字典的列数或列名不再匹配。",
                ),
                ManualSection(
                    "预览与质量提示",
                    bullets=(
                        "预览表显示当前方向各角度、各通道的相位，列多时可横向滚动。",
                        "质量提示会列出有效行、竞争峰、零数据行和有效秩等检查结果。",
                        "黄色或红色提示用于要求人工复核；提示本身不会阻止点击应用。",
                        "加载错误会弹出具体原因。修正源文件后重新加载，不需要重启程序。",
                    ),
                    note="质量提示是导入检查，不是项目验收结论。应用后仍要回到 1D/2D 页检查关注角度。",
                ),
            ),
        ),
        ManualChapter(
            "channel_patterns",
            "配置通道幅相",
            "为物理通道或虚拟通道加载水平/俯仰的幅度与相位数据，支持汇总文件和单通道文件。",
            (
                ManualSection(
                    "选择目标和数据槽",
                    bullets=(
                        "物理通道目标：表格列出 Tx1…和 Rx1…，适合按真实收发通道配置。",
                        "虚拟通道目标：表格列出 Tx1Rx1、Tx1Rx2…，适合直接配置组合通道。",
                        "每个目标都有四个独立槽：幅度-水平、幅度-俯仰、相位-水平、相位-俯仰。",
                        "未导入的槽保持理想，不要求一次把所有通道和四个槽全部填满。",
                    ),
                    note="切换物理/虚拟目标只改变当前表格和导入映射，不会清除另一类已经加载的数据。",
                ),
                ManualSection(
                    "导入汇总文件",
                    steps=(
                        "选择“物理通道”或“虚拟通道”目标。",
                        "点击对应的“加载汇总”按钮，明确本次文件属于幅度/相位以及水平/俯仰。",
                        "选择 CSV、TSV、XLSX 或 XLSM 文件。文件应包含角度列和多个数据列。",
                        "导入后检查表格每行显示的文件名与列名，并观察顶部通道幅相状态。",
                    ),
                    bullets=(
                        "物理目标按当前 Tx/Rx 通道规则和可识别列名映射。",
                        "虚拟目标按 Tx1Rx1、Tx1Rx2，直到最后一个 Tx/Rx 组合的顺序映射；显式通道列名优先。",
                        "角度列可使用 Theta、Angle、Azimuth、Az 或 Deg 等常见名称。",
                    ),
                    warning="汇总列数或列名与当前目标不匹配时会拒绝导入。不要靠增删空列绕过检查，应修正目标选择或源文件表头。",
                ),
                ManualSection(
                    "单通道修改、清除与生效时机",
                    steps=(
                        "在表格中选中一个通道。",
                        "点击底部对应“设置”按钮，给该通道加载一个数据文件。单通道文件使用角度列后的第一个数据列。",
                        "需要撤销某一通道时点击“清除选中通道”；需要全部恢复理想状态时点击“清空全部”。",
                        "返回主窗口后检查 1D/2D 图和顶部通道幅相状态。",
                    ),
                    bullets=(
                        "每次导入或清除都会立即重新计算；“完成”只关闭窗口，不提供回滚。",
                        "通道幅相不会写入本地 state.json，也不会写入阵面 JSON；重启程序后需要重新导入。",
                        "如果准备使用“通道幅相校准字典”，先完成本章配置，再到 DBF 字典窗口应用该模式。",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "files_reports",
            "阵面文件与性能报告",
            "区分可再次编辑的阵面坐标文件、当前会话配置和用于交付的 PDF/CSV/JSON 报告。",
            (
                ManualSection(
                    "导入与导出阵面 JSON",
                    steps=(
                        "使用“文件 > 导出阵面JSON”选择保存位置。默认建议放在 outputs 目录。",
                        "需要恢复坐标时，使用“文件 > 导入阵面JSON”选择文件。",
                        "导入成功后核对状态栏中的第一个 TX/RX、坐标范围和图中通道数量。",
                    ),
                    bullets=(
                        "文件保存 TX/RX 坐标，并附带导出时的 evaluation 快照，便于审阅。",
                        "重新导入时只恢复 TX/RX 坐标；evaluation 不会反向恢复频率、DBF 字典或通道幅相。",
                        "导入要求 TX 和 RX 都非空、各不超过 16 个，并使用受支持的版本和 λ 单位。",
                    ),
                    warning="阵面 JSON 不是完整工程包。要复现校准结果，还需保存原始字典、通道幅相文件和所用参数。",
                ),
                ManualSection(
                    "输出当前配置性能报告",
                    steps=(
                        "选择“文件 > 输出当前配置性能报告…”。若方位和俯仰都不可用，该功能不可执行。",
                        "选择 PDF 路径并填写报告标题。已有文件会在生成前询问是否覆盖。",
                        "分别设置可用方向的性能关注真角范围；起始角不得大于终止角。",
                        "设置角谱 Hold 真角范围，或勾选跟随关注范围。界面会显示按 1° 步进的帧数。",
                        "设置测角误差门限和 dB 图显示下限，并至少选择 dB 或模值中的一种角谱纵坐标。",
                        "按需勾选“同时导出可复现原始数据（CSV/JSON）”，然后点击“输出报告”。",
                    ),
                ),
                ManualSection(
                    "生成过程与输出内容",
                    bullets=(
                        "生成在后台执行，进度窗口会显示当前阶段，主窗口不会因绘图而长期无响应。",
                        "点击取消后，会等当前绘图步骤安全结束再停止。",
                        "PDF 包含当前配置摘要、关注范围统计和所选角谱页面；每种角谱单独占页。",
                        "选择原始数据后，会在报告旁生成数据目录，其中包含 CSV 和报告清单 JSON。",
                    ),
                    note="Hold 范围越大、选择的显示方式越多，报告页数和生成时间越长。交付前先用小范围生成一次样例，确认标题和显示下限。",
                ),
            ),
        ),
        ManualChapter(
            "shortcuts_state",
            "快捷键、撤销与启动恢复",
            "使用键盘提高编辑效率，并明确哪些内容会自动恢复、哪些内容必须另行保存。",
            (
                ManualSection(
                    "常用快捷键",
                    bullets=(
                        "Ctrl+O：导入阵面 JSON。",
                        "Ctrl+S：导出阵面 JSON。",
                        "Ctrl+Z：撤销阵列编辑。Ctrl+Y 或 Ctrl+Shift+Z：按当前操作系统标准重做阵列编辑。",
                        "Ctrl+R 或 Ctrl+G：重新计算并刷新全部视图。",
                        "Ctrl+F：聚焦频率输入框并选中现有内容。",
                        "Ctrl+1 / Ctrl+2 / Ctrl+3：切换物理与虚拟阵列、1D DBF、2D DBF。",
                        "方向键：移动当前选中的 TX/RX。",
                        "Delete：删除选中通道；无选择时进入删除模式。",
                        "Esc：退出删除模式、取消正在进行的拖动，或清除当前选择。",
                    ),
                    note="输入框获得焦点时，方向键和 Delete 保持文字编辑行为，不会误改阵列。",
                ),
                ManualSection(
                    "撤销和重做范围",
                    bullets=(
                        "可撤销：添加、删除、拖动、方向键移动、清空、自动排阵和导入阵面。",
                        "不可撤销：频率、竞争峰裕量、语言、DBF 显示、字典和通道幅相。",
                        "最多保留 50 步；执行新布局编辑后，原有重做分支会清空。",
                    ),
                    warning="通道幅相导入会立即生效且不进入撤销栈。导入前应确认目标和槽位，必要时保留源文件清单。",
                ),
                ManualSection(
                    "正常关闭后自动恢复",
                    bullets=(
                        "会恢复：语言、最近使用目录、频率、竞争峰裕量、DBF 显示方式、阵列坐标、窗口大小/位置、最大化状态、活动页签和分隔条比例。",
                        "DBF 字典模式及外部字典路径会尝试恢复；源文件不存在或无法读取时会退回安全模式。",
                        "不会恢复：通道幅相表格中的导入内容。下次启动需要重新导入。",
                        "自动恢复依赖正常关闭；异常终止时，最近一次会话修改可能尚未写入。",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "troubleshooting",
            "常见问题与排错",
            "从能力提示、输入恢复、文件导入、字典映射、报告生成和日志位置快速定位问题。",
            (
                ManualSection(
                    "图表为空或控件被禁用",
                    bullets=(
                        "1T1R：没有方向孔径，1D 和 2D 显示能力提示是正常状态。",
                        "只有一条轴有展开：在 1D 页使用有效方向；2D 页会提示返回 1D。",
                        "希望启用某个方向：拖开该方向上的 TX/RX，或使用自动排阵后再微调。",
                        "布局已改变但图未更新：按 Ctrl+R 或 Ctrl+G；仍无变化时查看状态栏是否恢复了无效输入。",
                    ),
                ),
                ManualSection(
                    "结果异常或突然跳变",
                    steps=(
                        "确认顶部显示的字典模式和通道幅相状态。",
                        "切回理想几何字典，判断异常来自布局还是外部数据。",
                        "检查虚拟阵列是否有大量重复点，并查看竞争峰裕量和截断原因。",
                        "如果方向完全相反，检查反向相位模式和导入字典的相位反向选项。",
                        "用 1D 拖动定位具体角度，再到 2D 复查，不要同时修改多个配置。",
                    ),
                    note="每次只改一项并记录前后状态，能更快判断问题来源。",
                ),
                ManualSection(
                    "文件或报告失败",
                    bullets=(
                        "阵面 JSON：检查文件版本、单位、tx/rx 非空、数量不超过 16，以及坐标是否为数字。",
                        "通道幅相：检查角度列、数据列、物理/虚拟目标、列数和通道名称；关闭占用文件的表格软件后重试。",
                        "外部字典：检查至少有一个方向文件、通道目标与当前阵列一致、表头完整且数据可解析。",
                        "性能报告：检查至少一个方向可用、范围起止顺序正确、至少选择 dB 或模值，并确认输出目录可写。",
                        "报告取消后仍显示处理中：等待当前绘图步骤结束，程序会安全停止。",
                    ),
                    warning="错误弹窗中的具体文字和“帮助 > 关于”所示日志路径是排错依据。提交问题时请同时提供日志、阵面 JSON、所用外部文件名和复现步骤。",
                ),
            ),
        ),
    )


def _en_chapters() -> tuple[ManualChapter, ...]:
    return (
        ManualChapter(
            "quick_start",
            "Quick start",
            "The shortest path from an empty layout to a repeatable check. Follow this chapter in order on your first run.",
            (
                ManualSection(
                    "Before you begin",
                    paragraphs=(
                        "At startup, the app restores the last layout, frequency, display mode, active page, and window arrangement. Check the three header badges for frequency, DBF dictionary, and channel amplitude/phase before starting a new task.",
                    ),
                    bullets=(
                        "For a clean start, open Physical & Virtual and select Clear; the layout returns to the 1T1R starter state.",
                        "If an array file already exists, use File > Import Array JSON. This restores Tx/Rx coordinates only.",
                        "Otherwise enter the T and R counts in Auto Array and select Apply Array. Both counts accept 1 through 16.",
                    ),
                    note="The status bar reports the latest action. If a result appears unchanged, read the status bar first.",
                ),
                ManualSection(
                    "Run a basic check",
                    steps=(
                        "Add, drag, or auto-arrange Tx/Rx elements and verify the channel names and positions. Coordinates are shown in λ.",
                        "Enter the operating frequency and press Enter or leave the field, then set the competing-peak margin.",
                        "Inspect unique and duplicate points in the virtual array, then read channel count, aperture, and resolution in the overview.",
                        "Open 1D DBF. Drag each true-angle marker or select Play to confirm that the peak follows continuously in azimuth and elevation.",
                        "When both axes have usable aperture, open 2D DBF and drag the crosshair through the angles of interest.",
                        "Save coordinates with File > Export Array JSON. Export a performance report when results need to be reviewed or delivered.",
                    ),
                ),
                ManualSection(
                    "Expected result",
                    bullets=(
                        "A usable axis shows its spectrum, true angle, estimated peak, and angle metrics.",
                        "An axis without aperture shows a neutral capability message instead of a flat spectrum or misleading heatmap.",
                        "Duplicate virtual points, boundary limits, and insufficient peak margin are called out in the plots, overview, or status text.",
                    ),
                    warning="Do not conclude from one static frame. Drag or play through the required angle range and verify the active dictionary and channel-data state.",
                ),
            ),
        ),
        ManualChapter(
            "workspace",
            "Main window and workspaces",
            "Learn what each area and page is for, and which information refreshes automatically after a layout change.",
            (
                ManualSection(
                    "Window areas",
                    bullets=(
                        "Menu bar: import/export, undo/redo, channel data, DBF dictionary, language, and help.",
                        "Header: global frequency, DBF dictionary, and channel amplitude/phase status.",
                        "Pages: Physical & Virtual, 1D DBF, and 2D DBF. Use the mouse or Ctrl+1, Ctrl+2, and Ctrl+3.",
                        "Overview sidebar: array size, virtual-channel use, aperture, resolution, and angle evaluation.",
                        "Command bar: frequency, competing-peak margin, Auto Array, and DBF display scale.",
                        "Status bar: the latest import, edit, playback, input recovery, or report action.",
                    ),
                ),
                ManualSection(
                    "Choose the right page",
                    bullets=(
                        "Physical & Virtual: edit real Tx/Rx positions, inspect virtual points, and read overview metrics.",
                        "1D DBF: inspect azimuth or elevation independently; one usable axis remains available even when the other is not.",
                        "2D DBF: inspect azimuth and elevation together; it requires usable aperture on both axes.",
                    ),
                    note="If 2D reports limited capability but one 1D axis is usable, work in 1D. Do not alter a correct single-axis design merely to make a 2D plot appear.",
                ),
                ManualSection(
                    "Resize the workspace",
                    steps=(
                        "Drag the splitter between the main plots and overview to allocate more room to either side.",
                        "After resizing the window, allow the short debounced refresh to complete before reading the plots.",
                        "Hover truncated file names or status text to see the complete tooltip.",
                    ),
                    bullets=(
                        "The minimum window size is 1100×650. On a small display, narrow the overview sidebar first.",
                        "Window geometry and splitter sizes are saved at normal close and restored inside the current screen work area.",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "layout_editing",
            "Edit the Tx/Rx layout",
            "Add, select, drag, nudge, delete, and auto-arrange channels. Coordinates are displayed in λ and dependent views update after each edit.",
            (
                ManualSection(
                    "Add channels or create an array",
                    steps=(
                        "Select +TX or +RX. The new channel is placed on an unused grid position to the right and becomes selected.",
                        "To replace the complete layout, enter T and R counts in Auto Array.",
                        "Select Apply Array or press Enter in a count field. The layout is replaced and all views refresh.",
                    ),
                    bullets=(
                        "Tx accepts 1–16 channels and Rx accepts 1–16 channels.",
                        "Add, auto-array, clear, import, drag, and keyboard moves are undoable.",
                        "Clear returns to a usable 1T1R starter layout; it does not create a zero-channel array.",
                    ),
                    warning="Apply Array and Clear replace existing coordinates. Export Array JSON first if the current positions must be retained.",
                ),
                ManualSection(
                    "Select, drag, and nudge",
                    steps=(
                        "Click a Tx or Rx in the physical plot to select it.",
                        "Drag with the left mouse button. The plot can expand near an edge. On release, the point snaps to the displayed 0.5λ grid and all results recalculate.",
                        "With a channel selected, use the arrow keys to move 0.5λ at a time. Arrow keys still edit text when an input field has focus.",
                        "Press Esc during a drag to restore the pre-drag position. Otherwise Esc clears the selection or exits Delete mode.",
                    ),
                    note="Channel numbers are aligned again after a move or deletion. Import channel-named external data only after the final layout and numbering are settled.",
                ),
                ManualSection(
                    "Delete and edit history",
                    steps=(
                        "Select a channel and press Delete to remove it.",
                        "With nothing selected, select Delete or press Delete to enter persistent Delete mode, then click multiple channels.",
                        "Select Delete again or press Esc to leave Delete mode.",
                        "Use Edit > Undo Layout Edit and Redo Layout Edit to move through recent layout changes.",
                    ),
                    bullets=(
                        "At least one Tx and one Rx must remain, so the last channel of either type cannot be deleted.",
                        "History keeps up to 50 steps and covers layout edits only, not frequency, dictionary, or channel amplitude/phase changes.",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "virtual_overview",
            "Virtual array and overview",
            "Confirm that Tx/Rx combinations form the expected virtual points, find duplicates, and see which axes have usable capability.",
            (
                ManualSection(
                    "Inspect virtual points",
                    steps=(
                        "After editing the physical array, inspect the virtual-array plot. Each point represents a Tx/Rx pair.",
                        "Hover a virtual point to read its channel pair and coordinates.",
                        "Compare unique virtual points with total virtual channels. A difference indicates overlapping points.",
                    ),
                    bullets=(
                        "Physical and virtual coordinates are displayed in λ; the overview also converts aperture to mm.",
                        "Duplicate points are not silently discarded. Utilization and duplicate notices include them.",
                    ),
                ),
                ManualSection(
                    "Read array metrics",
                    bullets=(
                        "Channels: current T×R size.",
                        "Virtual: unique points / all combinations and the resulting utilization.",
                        "Az/El aperture: effective spread on each axis, converted to mm at the operating frequency.",
                        "Az/El resolution: useful for comparing layouts; unavailable means no usable spread on that axis.",
                        "Capability: one usable axis keeps its 1D result; both axes are required for 2D.",
                    ),
                    note="Changing frequency changes the mm conversion but not positions displayed in λ. Use the same frequency when comparing layouts.",
                ),
                ManualSection(
                    "Read angle evaluation",
                    bullets=(
                        "No-fold range: the continuous true-angle interval available with the current settings.",
                        "Range error: check the maximum error against the task requirement.",
                        "Peak margin: use it with the command-bar criterion to judge whether the peak is clear enough.",
                        "Cut reason: explains why a side stops, such as a data edge, array boundary, or unreliable spectrum.",
                    ),
                    warning="Overview results depend on layout, frequency, dictionary, and channel data together. Recheck them after any of those changes.",
                ),
            ),
        ),
        ManualChapter(
            "global_controls",
            "Global controls and display",
            "The command bar controls physical-size conversion, reliability criteria, automatic layout, and plot scaling.",
            (
                ManualSection(
                    "Frequency",
                    steps=(
                        "Enter a positive value. A plain number, GHz suffix, or G suffix is accepted.",
                        "Press Enter or leave the field to apply it.",
                        "Check the header badge and aperture in mm to confirm the new frequency is active.",
                    ),
                    note="Blank, nonnumeric, zero, or negative input restores the most recent valid frequency and reports the recovery in the status bar.",
                ),
                ManualSection(
                    "Competing-peak margin",
                    steps=(
                        "Enter a dB value of 0 or greater.",
                        "Press Enter or leave the field, then inspect peak margin and cut reasons in angle evaluation.",
                    ),
                    paragraphs=(
                        "This is an operational acceptance criterion. A stricter value may reduce the usable interval; a looser value requires more careful inspection of competing peaks.",
                    ),
                    warning="Do not lower the margin only to enlarge the usable range. Use the project requirement or an agreed team value.",
                ),
                ManualSection(
                    "Auto Array and DBF display",
                    bullets=(
                        "Auto Array: enter T/R counts from 1 to 16 and apply a starter layout that can still be dragged and refined. The default arrangement is horizontal and normally creates azimuth aperture first; spread channels along y to enable elevation or 2D DBF.",
                        "dB: best for low-level regions, sidelobes, and competing peaks.",
                        "Magnitude: best for a quick view of the main-peak shape and heatmap boundaries.",
                        "Switching dB/magnitude changes display scaling only; layout, dictionary, and true angle remain unchanged.",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "dbf_1d",
            "1D DBF: azimuth and elevation",
            "Inspect each axis independently and use drag, play, pause, and stop to verify continuous peak tracking through the required range.",
            (
                ManualSection(
                    "Start an inspection",
                    steps=(
                        "Open 1D DBF. Azimuth is on the left and elevation is on the right.",
                        "Confirm that the true-angle line, estimated-peak marker, frame, and angle text are visible.",
                        "Hover the spectrum to read its angle and displayed value.",
                        "Move near the true-angle line, hold the left mouse button, and drag to a new angle.",
                    ),
                    bullets=(
                        "An axis without aperture shows a capability message and disables playback; the other axis remains usable when valid.",
                        "Dragging pauses the scan and immediately updates that axis and its metrics.",
                    ),
                ),
                ManualSection(
                    "Play, pause, and stop",
                    steps=(
                        "Select Play to scan the true angle from -90° to +90°.",
                        "Select the same button while running to pause at the displayed angle.",
                        "Select it again to resume. Select Stop to end the current axis scan.",
                        "When switching to another axis, follow the button and status-bar state to confirm which scan is active.",
                    ),
                    note="Use playback to find jumps or competitors, then drag through the suspicious interval for a closer check.",
                ),
                ManualSection(
                    "Judge the result",
                    bullets=(
                        "The estimated peak should follow the true angle without jumping far away in the required interval.",
                        "Read peak-to-true-angle error together with peak margin and the cut reason.",
                        "Use dB to inspect near-main competing peaks, then magnitude to confirm the main-peak outline.",
                    ),
                    warning="If the curve tracks in the opposite direction, first check Ideal Reversed Phase and the imported-dictionary phase-reverse option. Do not immediately rewrite array coordinates.",
                ),
            ),
        ),
        ManualChapter(
            "dbf_2d",
            "2D DBF heatmap",
            "When both axes are usable, inspect them together with independent playback and a draggable true-angle crosshair.",
            (
                ManualSection(
                    "Availability and markers",
                    bullets=(
                        "The heatmap is available only when azimuth and elevation both have usable aperture.",
                        "The white crosshair is the current true azimuth/elevation; the peak marker is the current estimate.",
                        "The color bar follows the dB/magnitude selection and the lightweight badge reports current angle or peak information.",
                    ),
                    note="If a capability message appears, add spread on the missing axis. If the design is intentionally single-axis, use 1D DBF instead.",
                ),
                ManualSection(
                    "Play and drag",
                    steps=(
                        "Select Play Az to change true azimuth only, or Play El to change true elevation only.",
                        "Both can run together. Selecting one active button pauses only that axis.",
                        "Select Stop to end both scans.",
                        "Move near the crosshair and drag with the left mouse button to set both true angles. Dragging stops automatic playback.",
                        "Hover the heatmap to read azimuth, elevation, and the displayed value.",
                    ),
                ),
                ManualSection(
                    "Recommended 2D review",
                    bullets=(
                        "Play azimuth and elevation separately before running both together.",
                        "Drag to the center, edges, and corners of the required region and record whether the peak remains near the true angle.",
                        "If several bright regions compete, switch to dB and return to 1D to isolate the affected axis.",
                    ),
                    warning="The heatmap locates issues but does not replace range statistics in the performance report.",
                ),
            ),
        ),
        ManualChapter(
            "dbf_dictionary",
            "Configure the DBF dictionary",
            "Choose one of four dictionary modes, preview either axis, and explicitly map imported data to physical or virtual channels.",
            (
                ManualSection(
                    "Four modes",
                    bullets=(
                        "Ideal geometric: default for checking layout and basic interaction.",
                        "Ideal reversed phase: a quick check of external-data or system direction conventions.",
                        "Channel amp/phase dictionary: uses the currently loaded channel data; missing channels remain ideal.",
                        "Imported CSV/XLSX: uses external simulation, calibration, or measured tables, loaded separately for azimuth and elevation.",
                    ),
                    note="Selecting a radio option changes the preview only. Select Apply Dictionary before the main window uses it; closing the dialog does not apply an unconfirmed mode.",
                ),
                ManualSection(
                    "Import an external dictionary",
                    steps=(
                        "Choose Physical channels for Tx1, Tx2, Rx1… or Virtual channels for Tx1Rx1, Tx1Rx2… ordering.",
                        "Select Load Az Dictionary or Load El Dictionary and choose CSV, TSV, XLSX, or XLSM.",
                        "Switch the Az/El preview and verify angle rows, channel columns, file name, and target type.",
                        "If required, enable imported phase reversal or 0° phase calibration and inspect the preview again.",
                        "Load at least one axis, choose Imported CSV/XLSX, and select Apply Dictionary.",
                    ),
                    bullets=(
                        "The table needs a header, angle information, and channel columns. Matching channel names are preferred.",
                        "Plain real values are read as phase angles; complex-form values are read as complex responses.",
                        "One axis may be loaded alone; the unloaded axis continues with default data.",
                    ),
                    warning="Finalize channel count and numbering before import. Later T/R changes can make external column counts or names incompatible.",
                ),
                ManualSection(
                    "Preview and quality callout",
                    bullets=(
                        "The preview lists phase by angle and channel; use horizontal scrolling for wide tables.",
                        "The quality callout summarizes valid rows, competing peaks, zero rows, and effective rank checks.",
                        "Amber and red callouts request review but do not block Apply.",
                        "Load errors show a specific reason. Correct the source and reload without restarting the app.",
                    ),
                    note="The callout checks the imported table; it is not a project acceptance result. Recheck required angles in 1D and 2D after applying.",
                ),
            ),
        ),
        ManualChapter(
            "channel_patterns",
            "Configure channel amplitude/phase",
            "Load horizontal/elevation amplitude and phase data for physical or virtual channels, using summary files or one channel at a time.",
            (
                ManualSection(
                    "Targets and data slots",
                    bullets=(
                        "Physical target: Tx1… and Rx1… rows for real transmit/receive channels.",
                        "Virtual target: Tx1Rx1, Tx1Rx2… rows for combined channels.",
                        "Each target has four independent slots: amplitude-horizontal, amplitude-elevation, phase-horizontal, and phase-elevation.",
                        "Unloaded slots remain ideal; a complete four-slot import for every channel is not required.",
                    ),
                    note="Changing the target changes the current table and import mapping; it does not clear data already loaded for the other target.",
                ),
                ManualSection(
                    "Import a summary file",
                    steps=(
                        "Choose Physical or Virtual as the target.",
                        "Select the relevant Load Summary button for amplitude/phase and horizontal/elevation.",
                        "Choose a CSV, TSV, XLSX, or XLSM file containing an angle column and multiple data columns.",
                        "After import, verify the file/column shown in each row and the header channel-data badge.",
                    ),
                    bullets=(
                        "Physical mapping follows current Tx/Rx rules and recognizable column names.",
                        "Virtual mapping follows Tx1Rx1, Tx1Rx2, through the final pair; explicit channel headers take priority.",
                        "Common angle headers such as Theta, Angle, Azimuth, Az, and Deg are recognized.",
                    ),
                    warning="A summary with incompatible columns is rejected. Correct the target selection or source headers instead of padding the file with empty columns.",
                ),
                ManualSection(
                    "Edit one channel, clear, and apply",
                    steps=(
                        "Select a row in the channel table.",
                        "Select the required Set button and load a file. A single-channel import uses the first data column after the angle column.",
                        "Use Clear Selected Channel to reset one row, or Clear All to return every channel to ideal.",
                        "Return to the main window and inspect 1D/2D results and the header badge.",
                    ),
                    bullets=(
                        "Every import or clear recalculates immediately. Done only closes the dialog and does not roll changes back.",
                        "Channel amplitude/phase is not written to state.json or Array JSON. Reimport it after restarting the app.",
                        "To use the Channel Amp/Phase dictionary, finish these imports first, then apply that mode in the dictionary dialog.",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "files_reports",
            "Array files and performance reports",
            "Separate editable coordinate files, current session settings, and PDF/CSV/JSON deliverables.",
            (
                ManualSection(
                    "Import and export Array JSON",
                    steps=(
                        "Use File > Export Array JSON and choose a location; the outputs folder is the default suggestion.",
                        "Use File > Import Array JSON when the coordinates need to be restored.",
                        "After import, verify the first Tx/Rx, coordinate range, and channel count reported by the status bar and plot.",
                    ),
                    bullets=(
                        "The file stores Tx/Rx coordinates and includes an evaluation snapshot for review.",
                        "Import restores Tx/Rx coordinates only. The evaluation snapshot does not restore frequency, DBF dictionary, or channel amplitude/phase.",
                        "Tx and Rx must both be nonempty, each limited to 16, with a supported version and λ unit.",
                    ),
                    warning="Array JSON is not a complete project package. Keep source dictionary/channel files and parameter notes to reproduce calibrated results.",
                ),
                ManualSection(
                    "Export a performance report",
                    steps=(
                        "Choose File > Export Current Performance Report. It is unavailable when neither axis has angle capability.",
                        "Choose the PDF path and title. Existing files require overwrite confirmation.",
                        "Set the performance-focus true-angle range for each usable axis; start must not exceed stop.",
                        "Set the spectrum Hold range or make it follow the focus range. The dialog reports the 1° frame count.",
                        "Set the angle-error threshold and dB display floor, and select at least one spectrum scale: dB or magnitude.",
                        "Optionally export reproducibility data (CSV/JSON), then select Export Report.",
                    ),
                ),
                ManualSection(
                    "Generation and output",
                    bullets=(
                        "Generation runs in the background and reports its stage in a progress dialog.",
                        "Cancel waits for the current rendering step to finish safely before stopping.",
                        "The PDF contains a configuration summary, focus-range statistics, and selected spectrum pages; each spectrum type uses its own page.",
                        "When raw data is selected, a neighboring directory contains CSV files and a report-manifest JSON.",
                    ),
                    note="A wider Hold range and more display scales create more pages. Generate a small sample first to verify the title and dB floor.",
                ),
            ),
        ),
        ManualChapter(
            "shortcuts_state",
            "Shortcuts, undo, and session restore",
            "Work faster with the keyboard and know what is restored automatically versus what must be saved separately.",
            (
                ManualSection(
                    "Keyboard shortcuts",
                    bullets=(
                        "Ctrl+O: import Array JSON.",
                        "Ctrl+S: export Array JSON.",
                        "Ctrl+Z / Ctrl+Y: undo / redo layout edits; the exact redo sequence follows the operating-system standard.",
                        "Ctrl+R or Ctrl+G: recalculate and refresh all views.",
                        "Ctrl+F: focus the frequency field and select its contents.",
                        "Ctrl+1 / Ctrl+2 / Ctrl+3: switch Physical & Virtual, 1D DBF, and 2D DBF.",
                        "Arrow keys: move the selected Tx/Rx.",
                        "Delete: remove the selected channel, or enter Delete mode when nothing is selected.",
                        "Esc: leave Delete mode, cancel an active drag, or clear selection.",
                    ),
                    note="When a text field has focus, arrow and Delete keys retain their text-edit behavior and do not change the layout.",
                ),
                ManualSection(
                    "Undo and redo scope",
                    bullets=(
                        "Undoable: add, delete, drag, arrow-key move, clear, auto-array, and Array JSON import.",
                        "Not undoable: frequency, peak margin, language, DBF display, dictionary, and channel amplitude/phase.",
                        "Up to 50 steps are retained. A new layout edit clears the old redo branch.",
                    ),
                    warning="Channel-data imports apply immediately and do not enter history. Verify target and slot, and keep a source-file list when needed.",
                ),
                ManualSection(
                    "Restored after a normal close",
                    bullets=(
                        "Restored: language, recent folders, frequency, peak margin, DBF display, layout, window geometry/state, active page, and splitter sizes.",
                        "The dictionary mode and external dictionary paths are restored when possible; missing or unreadable sources fall back safely.",
                        "Not restored: channel amplitude/phase table imports. Reimport them after restart.",
                        "Automatic state saving occurs during normal close; the latest changes may be missing after an abnormal termination.",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "troubleshooting",
            "Troubleshooting",
            "Resolve capability messages, recovered inputs, import mapping errors, report failures, and locate useful diagnostics.",
            (
                ManualSection(
                    "Blank plot or disabled controls",
                    bullets=(
                        "1T1R has no directional aperture, so neutral 1D/2D capability messages are expected.",
                        "With spread on one axis only, use the available 1D side; 2D directs you back to 1D.",
                        "To enable an axis, spread Tx/Rx along it or apply Auto Array and refine the positions.",
                        "If a layout changed but a view did not, press Ctrl+R or Ctrl+G and check whether the status bar restored invalid input.",
                    ),
                ),
                ManualSection(
                    "Unexpected peaks or jumps",
                    steps=(
                        "Confirm the dictionary and channel-data badges in the header.",
                        "Return to Ideal Geometric to separate a layout issue from an external-data issue.",
                        "Check virtual duplicates, peak margin, and cut reasons.",
                        "For completely reversed tracking, check reversed-phase modes and imported-dictionary phase reversal.",
                        "Use 1D dragging to isolate an angle, then verify it in 2D. Change only one setting at a time.",
                    ),
                    note="Recording the before/after state for one change at a time makes the source much easier to identify.",
                ),
                ManualSection(
                    "File or report failure",
                    bullets=(
                        "Array JSON: check version, unit, nonempty tx/rx lists, maximum 16 per type, and numeric coordinates.",
                        "Channel data: check the angle column, data columns, target, channel count/names, and close spreadsheet software that may hold the file.",
                        "External dictionary: load at least one axis, match the channel target to the current layout, and verify headers and parseable data.",
                        "Performance report: require a usable axis, ordered ranges, at least one dB/magnitude scale, and a writable output directory.",
                        "If cancellation still says busy, wait for the current rendering step to finish safely.",
                    ),
                    warning="Use the exact error message and the log path shown by Help > About. Include the log, Array JSON, source-file names, and reproduction steps in a support request.",
                ),
            ),
        ),
    )


def _ja_chapters() -> tuple[ManualChapter, ...]:
    return (
        ManualChapter(
            "quick_start",
            "クイックスタート",
            "空の配置から再現可能な確認を完了するまでの最短手順です。初回は上から順に操作してください。",
            (
                ManualSection(
                    "開始前の確認",
                    paragraphs=(
                        "起動時には前回終了時の配置、周波数、表示方式、選択ページ、ウィンドウ配置が復元されます。ヘッダーの周波数、DBF 辞書、チャネル振幅/位相の状態を確認してください。",
                    ),
                    bullets=(
                        "最初から作る場合は「物理・仮想アレイ」で「クリア」を選び、1T1R の初期配置に戻します。",
                        "配置ファイルがある場合は「ファイル > アレイJSONを読み込み」を使用します。読み込まれるのは TX/RX 座標だけです。",
                        "新規作成では下部の自動配置に T/R 数を入力し、「アレイを適用」を選びます。どちらも 1～16 です。",
                    ),
                    note="ステータスバーには直前の操作結果が表示されます。変化が見えない場合は、まずここを確認してください。",
                ),
                ManualSection(
                    "基本確認の実行",
                    steps=(
                        "TX/RX を追加、ドラッグ、または自動配置し、名称と位置を確認します。座標表示は λ です。",
                        "動作周波数を入力して Enter を押すかフォーカスを外し、続けて競合ピーク余裕を設定します。",
                        "仮想アレイの一意点と重複点を確認し、概要のチャネル数、開口、分解能を読みます。",
                        "「1D DBF」で真角度線をドラッグするか再生し、方位と仰角のピーク追従を確認します。",
                        "両軸に有効な開口がある場合は「2D DBF」で十字線を関心角度へドラッグします。",
                        "「ファイル > アレイJSONを書き出し」で座標を保存し、必要なら性能レポートを出力します。",
                    ),
                ),
                ManualSection(
                    "期待される表示",
                    bullets=(
                        "有効な軸には角度スペクトル、真角度、推定ピーク、測角指標が表示されます。",
                        "開口のない軸には、平坦な曲線や誤解を招くヒートマップではなく能力メッセージが表示されます。",
                        "仮想点の重複、境界制限、ピーク余裕不足はプロット、概要、または状態表示に示されます。",
                    ),
                    warning="1 枚の静止画だけで判断しないでください。対象角度をドラッグまたは再生し、使用中の辞書とチャネルデータ状態も確認します。",
                ),
            ),
        ),
        ManualChapter(
            "workspace",
            "メインウィンドウと3つの作業ページ",
            "各領域とページの用途、および配置変更後に自動更新される情報を説明します。",
            (
                ManualSection(
                    "ウィンドウの構成",
                    bullets=(
                        "メニュー：読み込み/書き出し、元に戻す/やり直し、チャネルデータ、DBF 辞書、言語、ヘルプ。",
                        "ヘッダー：周波数、DBF 辞書、チャネル振幅/位相のグローバル状態。",
                        "ページ：物理・仮想アレイ、1D DBF、2D DBF。Ctrl+1、Ctrl+2、Ctrl+3 でも切り替えられます。",
                        "右側概要：アレイ規模、仮想チャネル利用率、開口、分解能、測角評価。",
                        "下部コマンド：周波数、競合ピーク余裕、自動配置、DBF 表示方式。",
                        "ステータスバー：直前の読み込み、編集、再生、入力復元、レポート処理。",
                    ),
                ),
                ManualSection(
                    "ページの選択",
                    bullets=(
                        "物理・仮想アレイ：実際の TX/RX 位置を編集し、仮想点と概要を確認します。",
                        "1D DBF：方位または仰角を個別に確認します。一方だけ有効でも使用できます。",
                        "2D DBF：方位と仰角を同時に確認します。両軸に有効な開口が必要です。",
                    ),
                    note="2D が能力不足でも 1D の一方が有効なら、1D を使用してください。2D 表示のためだけに正しい単軸設計を変更する必要はありません。",
                ),
                ManualSection(
                    "表示領域の調整",
                    steps=(
                        "主プロットと右側概要の間のスプリッターをドラッグして幅を調整します。",
                        "ウィンドウ変更後は短い遅延更新が終わってからプロットを読みます。",
                        "省略されたファイル名や状態文字列は、ホバーして完全な tooltip を確認します。",
                    ),
                    bullets=(
                        "最小サイズは 1100×650 です。小さい画面では概要側を先に狭くします。",
                        "正常終了時にウィンドウ位置と分割比が保存され、次回は現在の画面内に復元されます。",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "layout_editing",
            "TX/RX 配置の編集",
            "チャネルの追加、選択、ドラッグ、キー移動、削除、自動配置を行います。座標は λ 表示で、変更後に関連表示が更新されます。",
            (
                ManualSection(
                    "追加と自動配置",
                    steps=(
                        "「+TX」または「+RX」を選びます。新しいチャネルは同種チャネルの右側の空きグリッドに追加され、選択状態になります。",
                        "配置全体を作り直す場合は、自動配置に T/R 数を入力します。",
                        "「アレイを適用」を選ぶか、数値欄で Enter を押します。現在配置が置換され、全表示が更新されます。",
                    ),
                    bullets=(
                        "TX と RX はそれぞれ 1～16 チャネルです。",
                        "追加、自動配置、クリア、読み込み、ドラッグ、キー移動は元に戻せます。",
                        "「クリア」はゼロチャネルではなく、1T1R の初期配置へ戻します。",
                    ),
                    warning="「アレイを適用」と「クリア」は現在座標を置換します。残す場合は先にアレイ JSON を書き出してください。",
                ),
                ManualSection(
                    "選択、ドラッグ、微調整",
                    steps=(
                        "物理アレイ上の TX または RX をクリックして選択します。",
                        "左ボタンでドラッグします。端に近づくと描画範囲が広がり、離すと 0.5λ 表示グリッドに合わせて再計算されます。",
                        "選択後に矢印キーで 1 回につき 0.5λ 移動します。入力欄にフォーカスがある場合は文字編集が優先されます。",
                        "ドラッグ中に Esc を押すと開始前へ戻ります。それ以外では選択解除または削除モード終了になります。",
                    ),
                    note="移動や削除後に同種チャネル番号が整列されます。Tx1、Rx1 などの名称を使う外部データは、配置確定後に読み込んでください。",
                ),
                ManualSection(
                    "削除と履歴",
                    steps=(
                        "チャネルを選択して Delete を押すと削除できます。",
                        "未選択時に「削除」または Delete を使うと連続削除モードになり、複数チャネルをクリックして削除できます。",
                        "もう一度「削除」を選ぶか Esc で終了します。",
                        "「編集 > 配置編集を元に戻す/やり直す」で最近の配置を復元します。",
                    ),
                    bullets=(
                        "最後の TX または RX は削除できず、各種 1 チャネル以上を維持します。",
                        "履歴は最大 50 ステップで、配置編集だけが対象です。周波数、辞書、チャネルデータは対象外です。",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "virtual_overview",
            "仮想アレイと概要",
            "TX/RX の組み合わせ、仮想点の重複、各軸の利用可能性を素早く確認します。",
            (
                ManualSection(
                    "仮想点の確認",
                    steps=(
                        "物理配置を編集した後、仮想アレイを確認します。各点は 1 組の TX/RX に対応します。",
                        "仮想点へカーソルを合わせ、チャネル組み合わせと座標を読みます。",
                        "一意仮想点数と全仮想チャネル数を比較します。差があれば重複点があります。",
                    ),
                    bullets=(
                        "物理/仮想座標は λ、概要の開口は mm でも表示されます。",
                        "重複点は無視されず、利用率と重複表示に反映されます。",
                    ),
                ),
                ManualSection(
                    "アレイ概要の読み方",
                    bullets=(
                        "チャネル数：現在の T×R。",
                        "仮想チャネル：一意点/全組み合わせ、および利用率。",
                        "方位/仰角開口：各軸の展開を現在周波数で mm 換算した値。",
                        "方位/仰角分解能：配置比較に使用します。利用不可はその軸に有効な展開がない状態です。",
                        "能力表示：一方だけ有効なら 1D、両方有効なら 2D が利用できます。",
                    ),
                    note="周波数変更で mm 換算は変わりますが、λ 表示の位置は変わりません。比較時は周波数を揃えてください。",
                ),
                ManualSection(
                    "測角評価の読み方",
                    bullets=(
                        "折り返しなし範囲：現在設定で連続利用できる真角度区間。",
                        "範囲内誤差：最大誤差がタスク要件を満たすか確認します。",
                        "ピーク余裕：下部の判定値と合わせ、ピークが十分明確か確認します。",
                        "終了理由：データ端、アレイ境界、角度スペクトル信頼性など、範囲が止まった理由です。",
                    ),
                    warning="概要は配置、周波数、辞書、チャネルデータの組み合わせ結果です。いずれかを変更した後は再確認してください。",
                ),
            ),
        ),
        ManualChapter(
            "global_controls",
            "共通設定と表示",
            "下部コマンドは寸法換算、信頼性判定、自動配置、グラフ表示に影響します。",
            (
                ManualSection(
                    "周波数",
                    steps=(
                        "正の数を入力します。数値だけ、GHz、または G の接尾辞を使用できます。",
                        "Enter を押すかフォーカスを外して適用します。",
                        "ヘッダーの周波数と概要の mm 開口を確認します。",
                    ),
                    note="空欄、数値以外、ゼロ、負数では直前の有効値に戻り、ステータスバーに表示されます。",
                ),
                ManualSection(
                    "競合ピーク余裕",
                    steps=(
                        "0 以上の dB 値を入力します。",
                        "Enter またはフォーカス移動で適用し、測角評価の余裕と終了理由を確認します。",
                    ),
                    paragraphs=(
                        "これは運用上の判定値です。厳しくすると利用範囲が狭くなる場合があり、緩くすると競合ピークの目視確認がより重要になります。",
                    ),
                    warning="範囲を広げるためだけに値を下げず、プロジェクト要件またはチーム合意値を使用してください。",
                ),
                ManualSection(
                    "自動配置と DBF 表示",
                    bullets=(
                        "自動配置：1～16 の T/R 数を入力し、後からドラッグ調整できる初期配置を作ります。既定は水平配置で通常は方位開口を先に作るため、仰角または 2D DBF には一部チャネルを y 方向へ広げます。",
                        "dB：低レベル領域、サイドローブ、競合ピークの確認向け。",
                        "振幅：主ピーク形状とヒートマップ境界の簡易確認向け。",
                        "表示切り替えは目盛だけを変更し、配置、辞書、真角度は変更しません。",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "dbf_1d",
            "1D DBF：方位と仰角",
            "方位と仰角を個別に確認し、ドラッグ、再生、一時停止、停止で対象範囲のピーク追従を調べます。",
            (
                ManualSection(
                    "確認の開始",
                    steps=(
                        "「1D DBF」を開きます。左が方位、右が仰角です。",
                        "真角度線、推定ピーク、フレーム、角度表示を確認します。",
                        "曲線へカーソルを合わせ、角度と表示値を読みます。",
                        "真角度線付近で左ボタンを押し、目的角度へドラッグします。",
                    ),
                    bullets=(
                        "開口のない軸は能力メッセージと再生無効状態になり、もう一方が有効ならそのまま使用できます。",
                        "真角度のドラッグで再生は一時停止し、曲線と指標がすぐ更新されます。",
                    ),
                ),
                ManualSection(
                    "再生、一時停止、停止",
                    steps=(
                        "「再生」を選ぶと真角度が -90° から +90° まで移動します。",
                        "再生中に同じボタンを選ぶと現在角度で一時停止します。",
                        "もう一度選ぶと再開し、「停止」で現在軸の走査を終了します。",
                        "別軸へ移る場合はボタンとステータスバーで有効な走査を確認します。",
                    ),
                    note="まず再生でジャンプや競合を探し、異常区間をドラッグで詳しく確認してください。",
                ),
                ManualSection(
                    "結果の判断",
                    bullets=(
                        "対象範囲では推定ピークが真角度を追従し、遠い位置へ突然移動しないことを確認します。",
                        "誤差だけでなく、ピーク余裕と終了理由も一緒に確認します。",
                        "dB で競合ピーク、振幅で主ピーク形状を確認します。",
                    ),
                    warning="追従方向が逆の場合は、まず逆位相辞書と読み込み辞書の位相反転設定を確認し、すぐに座標を変更しないでください。",
                ),
            ),
        ),
        ManualChapter(
            "dbf_2d",
            "2D DBF ヒートマップ",
            "両軸が有効な場合に、独立再生とドラッグ可能な十字線で方位と仰角を同時確認します。",
            (
                ManualSection(
                    "利用条件と表示",
                    bullets=(
                        "方位と仰角の両方に有効な開口がある場合のみ利用できます。",
                        "白い十字線が現在の真方位/真仰角、ピーク記号が推定位置です。",
                        "カラーバーは dB/振幅に連動し、上部バッジに現在角度またはピーク情報が表示されます。",
                    ),
                    note="能力メッセージが出た場合は不足軸の配置を広げます。単軸設計なら 1D DBF を使用してください。",
                ),
                ManualSection(
                    "再生とドラッグ",
                    steps=(
                        "「方位再生」は方位だけ、「仰角再生」は仰角だけを動かします。",
                        "両方を同時に再生できます。再度選んだ軸だけが一時停止します。",
                        "「停止」は両軸の再生を終了します。",
                        "十字線付近を左ドラッグすると両方の真角度を設定でき、自動再生は停止します。",
                        "ヒートマップへカーソルを合わせ、方位、仰角、表示値を読みます。",
                    ),
                ),
                ManualSection(
                    "確認手順",
                    bullets=(
                        "最初に方位と仰角を別々に再生し、その後に同時再生します。",
                        "対象領域の中心、端、四隅へ十字線を動かし、ピークが真角度付近にあるか記録します。",
                        "近い明領域が複数ある場合は dB 表示へ切り替え、1D で問題軸を特定します。",
                    ),
                    warning="ヒートマップは問題位置の確認用です。範囲統計が必要な場合は性能レポートを使用してください。",
                ),
            ),
        ),
        ManualChapter(
            "dbf_dictionary",
            "DBF 辞書の設定",
            "4 種類の辞書を選び、方位/仰角をプレビューし、外部データを物理または仮想チャネルへ明示的に割り当てます。",
            (
                ManualSection(
                    "4つのモード",
                    bullets=(
                        "理想幾何辞書：配置と基本動作を確認する既定モード。",
                        "理想逆位相辞書：外部データやシステムの方向規約を確認するモード。",
                        "チャネル振幅/位相辞書：現在読み込まれているチャネルデータを使用し、未設定チャネルは理想状態。",
                        "CSV/XLSX 辞書：外部シミュレーション、校正、実測テーブルを方位/仰角別に読み込みます。",
                    ),
                    note="ラジオボタンの選択はプレビューだけを更新します。「辞書を適用」を選ぶまでメイン画面には反映されません。",
                ),
                ManualSection(
                    "外部辞書の読み込み",
                    steps=(
                        "Tx1、Tx2、Rx1…なら「物理チャネル」、Tx1Rx1、Tx1Rx2…なら「仮想チャネル」を選びます。",
                        "「方位辞書読込」または「仰角辞書読込」で CSV、TSV、XLSX、XLSM を選びます。",
                        "方位/仰角プレビューを切り替え、角度行数、チャネル列数、ファイル名、対象を確認します。",
                        "必要なら位相反転または 0° 位相校正を有効にし、再度プレビューします。",
                        "少なくとも一方を読み込み、CSV/XLSX 辞書を選んで「辞書を適用」を押します。",
                    ),
                    bullets=(
                        "表にはヘッダー、角度情報、チャネル列が必要で、現在チャネルと一致する列名を推奨します。",
                        "通常の実数値は位相角、複数形式の値は複素応答として読み込まれます。",
                        "一方の軸だけでも読み込み可能で、未読み込み軸は既定データを使用します。",
                    ),
                    warning="読み込み前にチャネル数と番号を確定してください。後の T/R 変更で列数や列名が一致しなくなる場合があります。",
                ),
                ManualSection(
                    "プレビューと品質表示",
                    bullets=(
                        "プレビューには角度ごとの各チャネル位相が表示され、列が多い場合は横スクロールできます。",
                        "品質表示には有効行、競合ピーク、ゼロ行、有効ランクなどの確認結果が示されます。",
                        "黄/赤の表示は確認を促しますが、適用操作自体は止めません。",
                        "読み込みエラーには理由が表示されます。元ファイルを修正して再読み込みできます。",
                    ),
                    note="品質表示は読み込み確認であり、プロジェクト合否ではありません。適用後に 1D/2D で対象角度を確認してください。",
                ),
            ),
        ),
        ManualChapter(
            "channel_patterns",
            "チャネル振幅/位相の設定",
            "物理または仮想チャネルに水平/仰角の振幅と位相を、集約ファイルまたは単一チャネル単位で読み込みます。",
            (
                ManualSection(
                    "対象とデータ枠",
                    bullets=(
                        "物理対象：実 TX/RX の Tx1…、Rx1…を表示します。",
                        "仮想対象：組み合わせチャネルの Tx1Rx1、Tx1Rx2…を表示します。",
                        "各対象には振幅-水平、振幅-仰角、位相-水平、位相-仰角の 4 枠があります。",
                        "未読み込み枠は理想状態で、すべてを埋める必要はありません。",
                    ),
                    note="対象切り替えは表示と読み込み割り当てだけを変更し、もう一方へ読み込んだデータは消去しません。",
                ),
                ManualSection(
                    "集約ファイルの読み込み",
                    steps=(
                        "物理または仮想対象を選びます。",
                        "振幅/位相と水平/仰角に対応する「集約読込」を選びます。",
                        "角度列と複数データ列を含む CSV、TSV、XLSX、XLSM を選びます。",
                        "読み込み後、各行のファイル/列名とヘッダー状態を確認します。",
                    ),
                    bullets=(
                        "物理対象は現在の Tx/Rx 規則と認識可能な列名で割り当てます。",
                        "仮想対象は Tx1Rx1、Tx1Rx2 から最後の組み合わせ順で、明示列名を優先します。",
                        "Theta、Angle、Azimuth、Az、Deg などの角度列名を認識します。",
                    ),
                    warning="列が対象と一致しない集約ファイルは拒否されます。空列を追加せず、対象選択または表ヘッダーを修正してください。",
                ),
                ManualSection(
                    "単一チャネル、消去、反映",
                    steps=(
                        "表でチャネルを選択します。",
                        "必要な「設定」ボタンからファイルを読み込みます。単一チャネルでは角度列の後の最初のデータ列を使用します。",
                        "1 チャネルだけ戻す場合は「選択チャネルをクリア」、全体は「すべてクリア」を使用します。",
                        "メイン画面へ戻り、1D/2D とヘッダー状態を確認します。",
                    ),
                    bullets=(
                        "読み込み/消去のたびに即時再計算されます。「完了」は閉じるだけで、変更を戻しません。",
                        "チャネル振幅/位相は state.json やアレイ JSON に保存されず、再起動後は再読み込みが必要です。",
                        "チャネル振幅/位相辞書を使う場合は、本章の設定後に辞書画面でそのモードを適用します。",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "files_reports",
            "アレイファイルと性能レポート",
            "再編集用座標ファイル、現在セッション設定、提出用 PDF/CSV/JSON を区別します。",
            (
                ManualSection(
                    "アレイ JSON の読み込み/書き出し",
                    steps=(
                        "「ファイル > アレイJSONを書き出し」で保存先を選びます。既定候補は outputs です。",
                        "座標を戻す場合は「ファイル > アレイJSONを読み込み」を使用します。",
                        "読み込み後、ステータスバーの最初の TX/RX、座標範囲、プロットのチャネル数を確認します。",
                    ),
                    bullets=(
                        "ファイルは TX/RX 座標と、確認用の書き出し時 evaluation スナップショットを含みます。",
                        "再読み込みで復元されるのは TX/RX 座標だけです。evaluation から周波数、辞書、チャネルデータは復元されません。",
                        "TX/RX は空でなく各 16 以下、対応バージョンと λ 単位が必要です。",
                    ),
                    warning="アレイ JSON は完全なプロジェクト一式ではありません。校正結果の再現には辞書、チャネル元ファイル、設定値も保存してください。",
                ),
                ManualSection(
                    "性能レポートの出力",
                    steps=(
                        "「ファイル > 現在の設定性能レポートを出力」を選びます。両軸とも利用不可の場合は実行できません。",
                        "PDF パスとタイトルを指定します。既存ファイルは上書き確認されます。",
                        "利用可能な各軸の性能評価真角度範囲を設定し、開始角度を終了角度以下にします。",
                        "Hold 真角度範囲を設定するか、評価範囲への連動を選びます。1° ステップのフレーム数が表示されます。",
                        "誤差しきい値と dB 表示下限を設定し、dB/振幅の少なくとも一方を選びます。",
                        "必要なら再現用 CSV/JSON を選び、「レポートを出力」を押します。",
                    ),
                ),
                ManualSection(
                    "生成と出力内容",
                    bullets=(
                        "生成はバックグラウンドで行われ、進捗画面に処理段階が表示されます。",
                        "キャンセル後は現在の描画ステップが安全に終わってから停止します。",
                        "PDF には設定概要、評価範囲統計、選択した角度スペクトルが入り、各種類は別ページです。",
                        "生データを選ぶと、隣接ディレクトリに CSV とレポート一覧 JSON が作成されます。",
                    ),
                    note="Hold 範囲と表示種類を増やすほどページ数と時間が増えます。最初に小範囲でタイトルと dB 下限を確認してください。",
                ),
            ),
        ),
        ManualChapter(
            "shortcuts_state",
            "ショートカット、履歴、起動時復元",
            "キー操作を使い、何が自動復元され、何を別保存すべきか確認します。",
            (
                ManualSection(
                    "キーボード操作",
                    bullets=(
                        "Ctrl+O：アレイ JSON を読み込み。",
                        "Ctrl+S：アレイ JSON を書き出し。",
                        "Ctrl+Z / Ctrl+Y：配置編集を元に戻す/やり直す。やり直しは OS 標準操作に従います。",
                        "Ctrl+R または Ctrl+G：全表示を再計算して更新。",
                        "Ctrl+F：周波数欄へ移動し、現在文字列を選択。",
                        "Ctrl+1 / Ctrl+2 / Ctrl+3：物理・仮想、1D DBF、2D DBF を切り替え。",
                        "矢印キー：選択中 TX/RX を移動。",
                        "Delete：選択チャネルを削除。未選択時は削除モード。",
                        "Esc：削除モード終了、ドラッグ取消、または選択解除。",
                    ),
                    note="入力欄にフォーカスがある場合、矢印と Delete は文字編集となり、配置を変更しません。",
                ),
                ManualSection(
                    "元に戻す/やり直す範囲",
                    bullets=(
                        "対象：追加、削除、ドラッグ、矢印移動、クリア、自動配置、アレイ JSON 読み込み。",
                        "対象外：周波数、ピーク余裕、言語、DBF 表示、辞書、チャネル振幅/位相。",
                        "最大 50 ステップ。新しい配置編集後は以前のやり直し分岐が消去されます。",
                    ),
                    warning="チャネルデータは即時反映され履歴には入りません。対象とデータ枠を確認し、必要なら元ファイル一覧を残してください。",
                ),
                ManualSection(
                    "正常終了後に復元される項目",
                    bullets=(
                        "復元：言語、最近のフォルダー、周波数、ピーク余裕、DBF 表示、配置、ウィンドウ位置/状態、ページ、分割比。",
                        "辞書モードと外部辞書パスは復元を試み、元ファイルがない場合は安全なモードへ戻ります。",
                        "非復元：チャネル振幅/位相の読み込み内容。再起動後に再読み込みします。",
                        "状態保存は正常終了時です。異常終了では直前変更が保存されない場合があります。",
                    ),
                ),
            ),
        ),
        ManualChapter(
            "troubleshooting",
            "トラブルシューティング",
            "能力表示、入力復元、ファイル割り当て、レポート失敗、ログ位置を確認します。",
            (
                ManualSection(
                    "空のプロットまたは無効ボタン",
                    bullets=(
                        "1T1R には方向開口がないため、1D/2D の能力メッセージは正常です。",
                        "一方だけ展開がある場合は有効な 1D を使い、2D から 1D へ戻ります。",
                        "軸を有効にするには、その方向へ TX/RX を広げるか自動配置後に調整します。",
                        "配置変更後に更新されない場合は Ctrl+R/Ctrl+G を押し、ステータスバーで無効入力復元を確認します。",
                    ),
                ),
                ManualSection(
                    "ピーク異常またはジャンプ",
                    steps=(
                        "ヘッダーの辞書とチャネルデータ状態を確認します。",
                        "理想幾何辞書へ戻し、配置と外部データのどちらが原因か分けます。",
                        "仮想点重複、ピーク余裕、終了理由を確認します。",
                        "方向が完全に逆なら逆位相モードと読み込み位相反転を確認します。",
                        "1D ドラッグで角度を特定し、2D で確認します。設定は一度に 1 項目だけ変更します。",
                    ),
                    note="変更前後の状態を 1 項目ずつ記録すると、原因を早く特定できます。",
                ),
                ManualSection(
                    "ファイルまたはレポートの失敗",
                    bullets=(
                        "アレイ JSON：バージョン、単位、空でない tx/rx、各 16 以下、数値座標を確認。",
                        "チャネルデータ：角度列、データ列、対象、列数/名称を確認し、ファイルを使用中の表計算ソフトを閉じます。",
                        "外部辞書：少なくとも一軸を読み込み、対象と現在配置を一致させ、ヘッダーとデータを確認。",
                        "性能レポート：有効軸、範囲順序、dB/振幅の選択、書き込み可能な出力先を確認。",
                        "キャンセル後も処理中の場合は、現在の描画ステップが安全に終わるまで待ちます。",
                    ),
                    warning="エラー文字列と「ヘルプ > このアプリについて」のログパスを使用してください。問い合わせにはログ、アレイ JSON、元ファイル名、再現手順を添付します。",
                ),
            ),
        ),
    )


_CHAPTERS_BY_LANGUAGE = {
    "zh": _zh_chapters(),
    "en": _en_chapters(),
    "ja": _ja_chapters(),
}


def manual_chapters(language: str) -> tuple[ManualChapter, ...]:
    """Return all chapters in stable navigation order for ``language``.

    Unsupported or malformed language values intentionally fall back to Chinese,
    matching the application's existing localization behavior.
    """

    normalized = language.strip().lower() if isinstance(language, str) else "zh"
    if normalized not in _SUPPORTED_LANGUAGES:
        normalized = "zh"
    return _CHAPTERS_BY_LANGUAGE[normalized]


def _escape(value: str) -> str:
    return html.escape(str(value), quote=True)


def manual_chapter_html(chapter: ManualChapter) -> str:
    """Render one chapter as a safe, self-contained HTML document.

    Every content field is escaped before insertion.  The function therefore
    remains safe if a future caller builds a chapter from a translated resource
    or another non-code source.
    """

    parts = [
        "<!doctype html><html><head><meta charset=\"utf-8\"><style>",
        "body{font-family:'Microsoft YaHei UI','Segoe UI','Yu Gothic UI',sans-serif;"
        "color:#1f2937;background:#ffffff;line-height:1.62;margin:18px 22px 28px}",
        "h1{font-size:24px;font-weight:700;line-height:1.28;margin:0 0 8px;color:#172033}",
        "h2{font-size:17px;font-weight:650;line-height:1.35;margin:25px 0 9px;"
        "padding-bottom:7px;border-bottom:1px solid #d8dee8;color:#172033}",
        "p{font-size:14px;margin:7px 0}p.summary{font-size:14px;color:#526174;"
        "margin:0 0 18px;padding-bottom:14px;border-bottom:1px solid #e5eaf1}",
        "ol,ul{font-size:14px;margin:8px 0 10px 22px;padding:0}li{margin:5px 0;padding-left:3px}",
        ".callout{font-size:14px;margin:12px 0;padding:10px 12px;border-radius:8px;"
        "border:1px solid}.callout p{margin:0}.note{background:#eef6fd;border-color:#9cc8ed;"
        "color:#184f78}.warning{background:#fff7e6;border-color:#e7bd68;color:#714c00}",
        "</style></head><body>",
        f"<h1>{_escape(chapter.title)}</h1>",
        f"<p class=\"summary\">{_escape(chapter.summary)}</p>",
    ]
    for section in chapter.sections:
        parts.append(f"<h2>{_escape(section.heading)}</h2>")
        parts.extend(f"<p>{_escape(paragraph)}</p>" for paragraph in section.paragraphs)
        if section.steps:
            parts.append("<ol>")
            parts.extend(f"<li>{_escape(step)}</li>" for step in section.steps)
            parts.append("</ol>")
        if section.bullets:
            parts.append("<ul>")
            parts.extend(f"<li>{_escape(bullet)}</li>" for bullet in section.bullets)
            parts.append("</ul>")
        if section.note:
            parts.append(
                f"<div class=\"callout note\"><p>{_escape(section.note)}</p></div>"
            )
        if section.warning:
            parts.append(
                f"<div class=\"callout warning\"><p>{_escape(section.warning)}</p></div>"
            )
    parts.append("</body></html>")
    return "".join(parts)


def manual_chapter_search_text(chapter: ManualChapter) -> str:
    """Return all searchable plain text for a chapter, without HTML or markup."""

    values = [chapter.key, chapter.title, chapter.summary]
    for section in chapter.sections:
        values.append(section.heading)
        values.extend(section.paragraphs)
        values.extend(section.steps)
        values.extend(section.bullets)
        if section.note:
            values.append(section.note)
        if section.warning:
            values.append(section.warning)
    return "\n".join(value.strip() for value in values if value and value.strip())


__all__ = [
    "MANUAL_CHAPTER_IDS",
    "ManualChapter",
    "ManualSection",
    "manual_chapter_html",
    "manual_chapter_search_text",
    "manual_chapters",
]
