import { dictionaries, type TranslationKey } from "./translations";
import { useSettingsStore } from "../features/settings/settings-store";

export function useI18n() {
  const language = useSettingsStore((state) => state.language);

  return {
    language,
    direction: language === "ar" ? "rtl" : "ltr",
    t: (key: TranslationKey) => dictionaries[language][key],
  };
}
