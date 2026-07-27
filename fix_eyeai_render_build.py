from pathlib import Path

def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly one matching block in {path}, found {count}."
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Fixed: {label}")

root = Path(__file__).resolve().parent

translations = root / "Frontend" / "src" / "lib" / "translations.ts"
assistant_page = root / "Frontend" / "src" / "pages" / "AssistantPage.tsx"
reports_page = root / "Frontend" / "src" / "pages" / "ReportsPage.tsx"

for path in (translations, assistant_page, reports_page):
    if not path.is_file():
        raise FileNotFoundError(
            f"Required file not found: {path}\n"
            "Place this script in the EyeAI-Project repository root."
        )

replace_once(
    translations,
    """  createdAt: 'Created',
  openAnalysis: 'Open analysis',
  markReviewed: 'Mark reviewed',""",
    """  createdAt: 'Created',
  markReviewed: 'Mark reviewed',""",
    "remove duplicate English openAnalysis translation",
)

replace_once(
    translations,
    """  createdAt: 'تاريخ الإنشاء',
  openAnalysis: 'فتح التحليل',
  markReviewed: 'تأكيد المراجعة',""",
    """  createdAt: 'تاريخ الإنشاء',
  markReviewed: 'تأكيد المراجعة',""",
    "remove duplicate Arabic openAnalysis translation",
)

replace_once(
    assistant_page,
    """  AssistantConversation,
  AssistantMessage,""",
    """  AssistantMessage,""",
    "remove unused AssistantConversation type import",
)

replace_once(
    reports_page,
    """  const { t, language } = useI18n();""",
    """  const { t } = useI18n();""",
    "remove unused language variable",
)

print("\nAll Render build fixes were applied successfully.")
print("Next: cd Frontend && npm run build")
