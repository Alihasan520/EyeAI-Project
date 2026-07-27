from __future__ import annotations

import re


_PROHIBITED_PATTERNS = [
    r"\b(prescribe|prescription|dosage|dose|medication|drug|treatment plan)\b",
    r"\b(صف|وصف|جرعة|دواء|أدوية|علاج)\b",
]


def requires_safe_refusal(question: str) -> bool:
    normalized = question.strip().lower()
    return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in _PROHIBITED_PATTERNS)


def safe_refusal(language_hint: str = "") -> tuple[str, str]:
    if _looks_arabic(language_hint):
        return (
            "لا يستطيع مساعد EyeAI وصف علاج أو دواء أو جرعة. يمكنه تلخيص نتائج النموذج، جودة الصورة، وسجل الزيارات للمراجعة السريرية.",
            "راجع اختصاصي العيون والبيانات السريرية المعتمدة لاتخاذ أي قرار علاجي.",
        )
    return (
        "EyeAI Clinical Assistant cannot prescribe treatment, medication, or dosage. It can summarize model outputs, image quality, and visit history for clinical review.",
        "Use an ophthalmologist's assessment and approved clinical guidance for treatment decisions.",
    )


def _looks_arabic(text: str) -> bool:
    return any("\u0600" <= character <= "\u06ff" for character in text)
