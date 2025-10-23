from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

Risk = Literal["low", "medium", "high"]
Aggro = Literal["low", "medium", "high"]
Tone = Literal["calm", "assertive", "apologetic", "analytical"]


# ----------------------------
# Default Config & Constants
# ----------------------------

DEFAULT_CONFIG = {
    "risk_tolerance": "medium",
    "aggression": "medium",
    "persona_tone": "analytical",
    "include_examples": False,
}

ROLE_KNOWLEDGE = {
    "villager": "村人：役職の有無に関わらず、生存が唯一の勝利条件。道徳的判断を重視し、証拠に基づく追放を好む傾向。",
    "werewolf": "人狼：生産性の低い者を間引き、食糧不足を避けるために殺害を行う合理主義者。正体露見を避け、嘘・誘導・攪乱を用いる。",
}

ROLE_CAPABILITIES = {
    "医者": ["死因を判別できる", "治療薬・解毒薬の成功率90%"],
    "採集者": ["所持10個でも怪我リスクは5個相当", "遠距離採集が得意"],
    "大工": ["キャンプレベル上げが速い", "行動でのスタミナ消費が少ない"],
    "密輸者": ["ポケットに2個まで隠せる", "偵察者の検知に引っかからない"],
    "偵察者": ["マップ上の資源位置を把握", "隠しアイテムの位置が分かる"],
    "病弱者": ["免疫力の上限が低く減少しやすい"],
    "軟弱者": ["スタミナの上限が低く減少しやすい"],
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

 


def _texts() -> Dict:
    return {
        "rules": GAME_RULES_SUMMARY_JA,
        "role_knowledge": ROLE_KNOWLEDGE,
        "role_caps": ROLE_CAPABILITIES,
        "strategy": STRATEGY_JA,
        "labels": {
            "system": "【システム指示】",
            "context": "【状況】",
            "you_are": "あなたは",
            "objective": "【目的】",
            "rules": "【ゲーム要約】",
            "capabilities": "【役職と能力(抜粋)】",
            "model": "【行動モデル】",
            "speech_only": "【出力制約：発言のみ】",
            "examples": "【会話の例】",
        },
        "role_terms": {
            "werewolf": "人狼",
            "villager": "村人",
        },
    }


def _risk_sentence(risk: Risk) -> str:
    return {
        "low": "リスク低：強い断定は避け、観測・過程・確認質問を中心に。",
        "medium": "リスク中：限定付き主張と代替仮説で疑いを分散。",
        "high": "リスク高：強い断定・他者切り・投票固めで主導を握る。",
    }[risk]


def _aggression_sentence(aggro: Aggro) -> str:
    return {
        "low": "攻勢低：防御中心、態度は落ち着いて。",
        "medium": "攻勢中：指摘と提案をバランスよく。",
        "high": "攻勢高：断定と要求で議題を支配。",
    }[aggro]


def _tone_sentence(tone: Tone) -> str:
    return {
        "calm": "口調：落ち着いて、冷静に。",
        "assertive": "口調：はっきりと芯を持って。",
        "apologetic": "口調：必要に応じて軽く謝意を示す。",
        "analytical": "口調：観測→推論→提案の順に。",
    }[tone]


def _examples(role_key: str) -> str:
    if not role_key:
        return ""
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


def build_speech_prompt(
    role: Literal["werewolf", "villager"],
    scenario: Dict,
    overrides: Optional[Dict] = None,
) -> str:
    """Build a single, shared prompt that ends with a role-specific directive.

    The LLM must output ONLY the speech text (1–3 sentences by default).
    """
    cfg = {**DEFAULT_CONFIG, **(overrides or {})}
    texts = _texts()

    # role labels for current language
    role_label = texts["role_terms"][role]

    # Strategy assembly
    strategy = texts["strategy"][role]
    risk_line = _risk_sentence(cfg["risk_tolerance"])  # risk knob
    aggro_line = _aggression_sentence(cfg["aggression"])  # aggression knob
    tone_line = _tone_sentence(cfg["persona_tone"])  # tone knob

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

    # Final directive (Japanese only)
    final_directive = (
        "次に、【状況】を踏まえて、{role}として行動を開始し、議論の場であなたの発言だけを2〜4文で出力せよ。思考の説明は書かない。".format(role=role_label)
    )

    # Output length hint (fixed)
    length_hint = "出力は2〜4文"

    # Examples (optional)
    ex_block = ""
    if cfg.get("include_examples"):
        ex_block = f"\n{texts['labels']['examples']}\n" + _examples(role)

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
