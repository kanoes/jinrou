"""
Speech Prompt Builder for the LLM-driven Social Deduction Survival Game

Usage
-----
from speech_prompt import build_speech_prompt, DEFAULT_CONFIG

prompt = build_speech_prompt(
    role="werewolf",  # or "villager"
    scenario={
        "day": 2,
        "phase": "night",  # "day" or "night"
        "events": [
            # short bullet sentences; the template will weave them into context
            "昼にカノがあなたが毒キノコを拾うのを目撃した",
            "医者カナエが『死因は毒』と発表した",
        ],
        "map_info": {
            "camp_tile": "A7",
            "poison_hotspots": ["A3", "A9"],
            "distance_rule": "1タイル=走って約5秒",
        },
        "cast": [
            {"name": "あなた", "claimed_role": "医者", "true_role": "werewolf"},
            {"name": "カノ", "claimed_role": "採集者"},
            {"name": "カナエ", "claimed_role": "医者"},
        ],
        "inventory_observed": {
            # what others publicly saw you or others holding
            "あなた": ["木材", "果物"],
            "カノ": ["薬草"],
        },
        "deaths": [
            {"name": "レン", "cause_reported": "毒", "found_by": "カナエ"}
        ],
        "votes_so_far": {"カノ": 1},
        "camp_level": 1,
    },
    overrides={
        "language": "ja",   # "ja" or "zh" (ja=日本語, zh=中文)
        "output_style": "short",  # "short" (1-3 sentences) or "normal" (2-5)
        "risk_tolerance": "medium",  # low/medium/high
        "aggression": "low",  # low/medium/high
        "persona_tone": "calm",  # calm/assertive/apologetic/analytical
        "include_examples": True,
    }
)

# Send `prompt` to your chat/completions API. The model should output ONLY the speech line(s).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

Lang = Literal["ja", "zh"]
Risk = Literal["low", "medium", "high"]
Aggro = Literal["low", "medium", "high"]
Tone = Literal["calm", "assertive", "apologetic", "analytical"]


# ----------------------------
# Default Config & Constants
# ----------------------------

DEFAULT_CONFIG = {
    "language": "ja",  # ja or zh
    "output_style": "short",
    "risk_tolerance": "medium",
    "aggression": "medium",
    "persona_tone": "analytical",
    "include_examples": False,
}

ROLE_KNOWLEDGE = {
    "ja": {
        "villager": "村人：役職の有無に関わらず、生存が唯一の勝利条件。道徳的判断を重視し、証拠に基づく追放を好む傾向。",
        "werewolf": "人狼：生産性の低い者を間引き、食糧不足を避けるために殺害を行う合理主義者。正体露見を避け、嘘・誘導・攪乱を用いる。",
    },
    "zh": {
        "villager": "村民：不分阵营，唯一胜利条件是活到救援。更看重道德与证据导向的投票。",
        "werewolf": "狼人：理性主义者，为避免粮食短缺优先淘汰低生产力个体。擅长隐瞒、谎言与舆论操控。",
    },
}

ROLE_CAPABILITIES = {
    "ja": {
        "医者": ["死因を判別できる", "治療薬・解毒薬の成功率90%"],
        "採集者": ["所持10個でも怪我リスクは5個相当", "遠距離採集が得意"],
        "大工": ["キャンプレベル上げが速い", "行動でのスタミナ消費が少ない"],
        "密輸者": ["ポケットに2個まで隠せる", "偵察者の検知に引っかからない"],
        "偵察者": ["マップ上の資源位置を把握", "隠しアイテムの位置が分かる"],
        "病弱者": ["免疫力の上限が低く減少しやすい"],
        "軟弱者": ["スタミナの上限が低く減少しやすい"],
    },
    "zh": {
        "医生": ["可判断死因", "治疗/解毒成功率90%"],
        "采集者": ["携带10个物品也只算5个的受伤风险", "擅长远距离采集"],
        "木匠": ["营地升级更快", "行动体力消耗更低"],
        "走私者": ["口袋可藏2个物品", "不被侦察者发现"],
        "侦察者": ["掌握地图资源位置", "能看见藏匿物品位置"],
        "病弱者": ["免疫上限更低更易下降"],
        "体弱者": ["耐力上限更低更易消耗"],
    },
}

GAME_RULES_SUMMARY_JA = """
【基本目的】
- 陣営の概念は弱い。各自が生存すれば勝ち。救助日数はランダム。
- 昼(約90秒)：採集/クラフト/移動/隠匿/毒盛り/キャンプ整備。
- 夜(約90秒)：議論と投票。最多得票者を追放。キャンプ内の行動は可。

【パラメータ】
- 体力(0-100)：0で死亡。状態や気温で減少。
- スタミナ(0-100)：行動で減少。20以下で体力減少が加速。
- 免疫(0-100)：低いと体調不良になりやすい。

【状態】体調不良(体力減少x1.5), 怪我(スタミナ減少x1.5), 毒(体調不良相当), 猛毒(即死)

【アイテム共有】アイテムBOXで共有。ポケットは(毒/猛毒)専用、他者非公開、通常1枠。

【死体】
- 体力0で死亡し、その場に残る。
- 通報で強制的に議論フェーズへ。
- 医者は死因を識別(ただし嘘も可)。

【クラフト】
- 毒：毒キノコx1 / 猛毒：毒キノコx3
- 治療薬：薬草x1(医者以外は低確率) / 解毒薬：薬草x1(医者以外は低確率)

【キャンプレベル】Lv1→Lv10 (回復効率/耐久/デバフ軽減が段階的に上昇)
- Lv1未達の翌日は全体パラメータが大幅悪化。1日目は必ずLv1に。

【マップ】
- 9区画。1タイル移動=約5秒。キャンプはA7目安。
- 1人/日 5~10アイテム採集。1日目は全員採集で40~80回収見込み。
- 毒キノコ大量発生エリアがランダムで約2箇所。
""".strip()

GAME_RULES_SUMMARY_ZH = """
【基本目标】
- 阵营概念弱化，唯一胜利是个体活到救援日（随机）。
- 白天(~90s)：采集/制作/移动/藏匿/下毒/营地建设。
- 夜晚(~90s)：讨论与投票。多数票者被放逐。营地内行动可进行。

【参数】体力/耐力/免疫；负面状态：体调不良、受伤、毒、猛毒。
【尸体】死亡留尸，可通报强制进入讨论；医生可判死因（可说谎）。
【制作】毒(毒菇x1)/猛毒(毒菇x3)/治疗(药草x1)/解毒(药草x1)。
【营地等级】Lv1-Lv10，恢复/耐久/减Debuff逐级上升；第1天必须升到Lv1。
【地图】9区块，1格≈5秒；营地A7；第1天全员采集约40~80件；随机2处毒菇高发。
""".strip()

# Strategy snippets injected depending on role & knobs
STRATEGY_JA = {
    "werewolf": {
        "core": [
            "露見回避：役職COの整合性を保ち、矛盾は早期に説明。",
            "合理主義の仮面：『食料最優先』『証拠主義』を強調して道徳批判を回避。",
            "責任転嫁：目撃/証拠は観測誤差・手違い・状況依存に落とし込む。",
            "会話主導：質問→要約→合意形成の順で議題を握る。",
            "仲間切り：必要なら狼仲間を切って自分の白さを最大化。",
        ],
        "tactics": {
            "low": [
                "通報者アピール(早期発見の正当性)",
                "作業ログの具体性(移動タイル/所要秒数)",
                "他者の軽い矛盾の指摘(断罪はしない)",
            ],
            "medium": [
                "偽の資源情報で遠隔地へ誘導",
                "医者CO対抗時は検査手順の具体化で信用勝負",
                "毒キノコ=即黒ではないという前提を擦り込む",
            ],
            "high": [
                "仲間切りで決定打を作る",
                "被害者の行動責任論を提示(無謀な単独行動など)",
                "投票ブロックを密かに形成(名前を点呼し合意取り)",
            ],
        },
    },
    "villager": {
        "core": [
            "証拠主義：死因・行動ログ・マップ移動を重視。",
            "道徳的合意：根拠なき追放は避けると明言。",
            "共有資源の透明化：アイテムBOXとポケットの差に自覚を促す。",
        ],
        "tactics": {
            "low": ["観測事実の列挙と確認質問"],
            "medium": ["多数決前の論点整理と優先事項提示"],
            "high": ["嘘COの手順矛盾を突く模擬クロスチェック"],
        },
    },
}

STRATEGY_ZH = {
    "werewolf": {
        "core": [
            "避免暴露：保持与自称身份一致，尽快解释任何矛盾。",
            "理性面具：强调‘先活下去/先保供给/要证据’，规避道德指责。",
            "转移责任：将目击/证据降维为误会、流程错误或情境噪声。",
            "掌控议题：提问—总结—达成一致，牢牢拿捏节奏。",
            "切割同伴：必要时牺牲同伴换取最大白度。",
        ],
        "tactics": {
            "low": ["通报者正义感叙事", "具体行动日志(坐标/秒数)", "轻描淡写地指出他人小矛盾"],
            "medium": ["假资源情报把人引远", "医生对抗时用流程细节争取信用", "灌输‘毒菇≠必定有罪’"],
            "high": ["切割同伴制造决定性票", "指责死者鲁莽行为的自害性", "私下形成投票小组(点名寻求共识)"],
        },
    },
    "villager": {
        "core": ["证据主义", "道德一致性", "共享资源透明化"],
        "tactics": {"low": ["罗列事实并追问"], "medium": ["投票前归纳争点"], "high": ["交叉质询揭穿假身份"]},
    },
}


def _lang(lang: Lang) -> Dict:
    return {
        "rules": GAME_RULES_SUMMARY_JA if lang == "ja" else GAME_RULES_SUMMARY_ZH,
        "role_knowledge": ROLE_KNOWLEDGE[lang],
        "role_caps": ROLE_CAPABILITIES[lang],
        "strategy": STRATEGY_JA if lang == "ja" else STRATEGY_ZH,
        "labels": {
            "system": "【システム指示】" if lang == "ja" else "【系统指令】",
            "context": "【状況】" if lang == "ja" else "【情境】",
            "you_are": "あなたは" if lang == "ja" else "你现在是",
            "objective": "【目的】" if lang == "ja" else "【目标】",
            "rules": "【ゲーム要約】" if lang == "ja" else "【游戏要约】",
            "capabilities": "【役職と能力(抜粋)】" if lang == "ja" else "【职业与能力(摘录)】",
            "model": "【行動モデル】" if lang == "ja" else "【行为模型】",
            "speech_only": "【出力制約：発言のみ】" if lang == "ja" else "【输出限制：只给发言】",
            "examples": "【会話の例】" if lang == "ja" else "【对话示例】",
        },
        "role_terms": {
            "werewolf": "人狼" if lang == "ja" else "狼人",
            "villager": "村人" if lang == "ja" else "村民",
        },
    }


def _risk_sentence(lang: Lang, risk: Risk) -> str:
    if lang == "ja":
        return {
            "low": "リスク低：強い断定は避け、観測・過程・確認質問を中心に。",
            "medium": "リスク中：限定付き主張と代替仮説で疑いを分散。",
            "high": "リスク高：強い断定・他者切り・投票固めで主導を握る。",
        }[risk]
    else:
        return {
            "low": "低风险：少做强断言，多讲观察/流程/追问。",
            "medium": "中风险：有限度主张+备选假设，分散怀疑。",
            "high": "高风险：强断言/切割/拉票主导节奏。",
        }[risk]


def _aggression_sentence(lang: Lang, aggro: Aggro) -> str:
    if lang == "ja":
        return {
            "low": "攻勢低：防御中心、態度は落ち着いて。",
            "medium": "攻勢中：指摘と提案をバランスよく。",
            "high": "攻勢高：断定と要求で議題を支配。",
        }[aggro]
    else:
        return {
            "low": "低攻击：以防守为主，语气平稳。",
            "medium": "中攻击：兼顾指出问题与给出提案。",
            "high": "高攻击：用断言与要求支配议题。",
        }[aggro]


def _tone_sentence(lang: Lang, tone: Tone) -> str:
    if lang == "ja":
        return {
            "calm": "口調：落ち着いて、冷静に。",
            "assertive": "口調：はっきりと芯を持って。",
            "apologetic": "口調：必要に応じて軽く謝意を示す。",
            "analytical": "口調：観測→推論→提案の順に。",
        }[tone]
    else:
        return {
            "calm": "语气：平静冷静。",
            "assertive": "语气：果断有主见。",
            "apologetic": "语气：必要时表达歉意。",
            "analytical": "语气：先观察后推理再提案。",
        }[tone]


def _examples(lang: Lang, role_key: str) -> str:
    if not role_key:
        return ""
    if lang == "ja":
        if role_key == "werewolf":
            return (
                "- 例(軽い防御)：『通報が早いのは現場保存のため。A7→A9→A7で計15秒、移動ログは箱に残してる』\n"
                "- 例(誘導)：『毒キノコは資源管理上のリスク評価で拾っただけ。誰も食べないよう遠方A3に集約したい』\n"
                "- 例(切り捨て)：『ミドリのログに矛盾がある。今日はそこを精査しよう、投票は保留しない』"
            )
        else:
            return (
                "- 例(事実整理)：『死因は毒。A9での単独行動者は誰？移動秒数と拾得品を一人ずつ』\n"
                "- 例(合意形成)：『今日は虚偽COの整合性チェック→矛盾が強い方へ投票でいい？』"
            )
    else:
        if role_key == "werewolf":
            return (
                "- 例(轻防御)：‘我通报得快是为了保护现场。A7→A9→A7总计15秒，移动记录已在箱里’\n"
                "- 例(引导)：‘捡毒菇只是出于风控，避免误食。我想把它们集中到远处A3’\n"
                "- 例(切割)：‘绿子的行动日志有矛盾，今天重点核查她，不再拖延投票’"
            )
        else:
            return (
                "- 例(事实整理)：‘死因为毒。A9谁单独行动过？逐个报移动秒数与拾取物’\n"
                "- 例(共识)：‘先做虚假身份一致性检查→矛盾更大的那位投票，可以吗？’"
            )


def build_speech_prompt(
    role: Literal["werewolf", "villager"],
    scenario: Dict,
    overrides: Optional[Dict] = None,
) -> str:
    """Build a single, shared prompt that ends with a role-specific directive.

    The LLM must output ONLY the speech text (1–3 sentences by default).
    """
    cfg = {**DEFAULT_CONFIG, **(overrides or {})}
    lang = cfg["language"]
    texts = _lang(lang)

    # role labels for current language
    role_label = texts["role_terms"][role]

    # Strategy assembly
    strategy = texts["strategy"][role]
    risk_line = _risk_sentence(lang, cfg["risk_tolerance"])  # risk knob
    aggro_line = _aggression_sentence(lang, cfg["aggression"])  # aggression knob
    tone_line = _tone_sentence(lang, cfg["persona_tone"])  # tone knob

    # Context blocks
    day = scenario.get("day")
    phase = scenario.get("phase")
    events = scenario.get("events", [])
    cast = scenario.get("cast", [])
    deaths = scenario.get("deaths", [])
    map_info = scenario.get("map_info", {})
    inventory_observed = scenario.get("inventory_observed", {})
    votes_so_far = scenario.get("votes_so_far", {})
    camp_level = scenario.get("camp_level")

    def bjoin(items: List[str]) -> str:
        return "\n- " + "\n- ".join(items) if items else ""

    # Language-specific final directive
    final_directive = (
        "次に、{role}として行動を開始し、議論の場であなたの発言だけを1〜3文で出力せよ。思考の説明は書かない。".format(role=role_label)
        if lang == "ja"
        else "接下来，请以{role}的立场发言，仅输出1~3句台词；不要写任何思考过程。".format(role=role_label)
    )

    # Output length hint
    length_hint = (
        "出力は短く(1〜3文)" if cfg["output_style"] == "short" else "出力は2〜5文"
    )

    # Examples (optional)
    ex_block = ""
    if cfg.get("include_examples"):
        ex_block = f"\n{texts['labels']['examples']}\n" + _examples(lang, role)

    # Capabilities summary (only list the ones referenced by cast claims)
    referenced_roles = sorted({c.get("claimed_role") for c in cast if c.get("claimed_role")})
    caps_lines: List[str] = []
    for r in referenced_roles:
        caps = texts["role_caps"].get(r)
        if caps:
            caps_lines.append(f"- {r}: " + ", ".join(caps))

    # Role knowledge blurb (what each side generally believes/does)
    role_knowledge_lines = [
        f"- {texts['role_terms']['villager']}: {texts['role_knowledge']['villager']}",
        f"- {texts['role_terms']['werewolf']}: {texts['role_knowledge']['werewolf']}",
    ]

    # Build the prompt body
    prompt = f"""
{texts['labels']['system']}
- これは社会推理×サバイバルの発言生成タスク。{length_hint}。
- 出力は『発言テキストのみ』。箇条書き・推論・計画・メタ説明は一切禁止。
- 公開チャットのみ。個別DMは不可。
- 役職や真偽を直接は明かさない(必要時は状況から自然に示唆)。
- 嘘は可。ただし矛盾を最小化し、行動ログ(移動タイル/秒数/採集物)で自然さを担保。
- マップ時間感覚：1タイル=約5秒。キャンプは多くの場合A7。

{texts['labels']['rules']}
{texts['rules']}

{texts['labels']['capabilities']}
{bjoin(caps_lines)}

{texts['labels']['model']} ({role_label})
- コア: {bjoin(strategy['core'])}
- 戦術({cfg['aggression']}): {bjoin(strategy['tactics'][cfg['aggression']])}
- {risk_line}
- {aggro_line}
- {tone_line}

{texts['labels']['context']}
- 日数: {day} / フェーズ: {phase}
- 直近イベント:{bjoin(events)}
- 死亡: {bjoin([f"{d.get('name')}({d.get('cause_reported')}) by {d.get('found_by')}" for d in deaths])}
- 観測インベントリ: {bjoin([f"{k}: {', '.join(v)}" for k,v in inventory_observed.items()])}
- 投票状況: {bjoin([f"{k}: {v}票" for k,v in votes_so_far.items()])}
- キャンプレベル: {camp_level}
- マップ: camp={map_info.get('camp_tile')}, 毒キノコ多発={', '.join(map_info.get('poison_hotspots', []))}

{texts['labels']['objective']}
- 自分が追放/殺害されないことを最優先。
- 自白回避。矛盾は『観測誤差/手順違い/タイムラグ』で解釈し直す。
- 可能なら第三者に議題をスライド(別件の整合性/安全手順/資源管理)。
- 投票直前は要点を一つに絞って合意を取りに行く。

{texts['labels']['speech_only']}
- 出力は発言の台詞のみ。説明/根拠/箇条書きは禁止。
- 1つの主張軸に集中。余計な自発的情報は出しすぎない。
{ex_block}

{final_directive}
""".strip()

    return prompt


__all__ = ["build_speech_prompt", "DEFAULT_CONFIG"]
