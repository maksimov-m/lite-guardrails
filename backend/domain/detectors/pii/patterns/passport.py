import datetime as dt
import re

from backend.domain.detectors.pii.patterns.base import PiiPattern

# Год изготовления бланка (цифры 3-4 серии) правдоподобен, если формат 4+6 уже
# существовал (введён в 1997) и год не в будущем (буфер +1 — допускается
# отклонение бланка на 1-3 года). Границы намеренно мягкие: задача — срезать
# явный мусор, не потеряв ни одного настоящего паспорта.
_LEGACY_YEARS_2D = (97, 98, 99)
# Коды регионов паспортных серий: 01..92 покрывают все реальные (включая 91/92 —
# Крым/Севастополь). 00 и 93..99 не используются. Диапазон — самый мягкий фильтр,
# при необходимости заменяется точным списком кодов ОКАТО/ГУВМ.
_MIN_REGION, _MAX_REGION = 1, 92


def _is_sequential(digits: str) -> bool:
    """Строгая монотонная лесенка по модулю 10: 1234567890 / 0123456789 / 9876543210."""
    diffs = {(int(digits[i + 1]) - int(digits[i])) % 10 for i in range(len(digits) - 1)}
    return diffs == {1} or diffs == {9}


class PassportRfPattern(PiiPattern):
    name = "passport_rf"
    regex = r"(?<!\d)\d{2}\s?\d{2}\s?\d{6}(?!\d)"

    def is_valid(self, value: str) -> bool:
        """Мягкая структурная валидация. У паспорта РФ НЕТ контрольной суммы
        (в отличие от ИНН/СНИЛС), поэтому проверяем правдоподобие серии и
        отбрасываем вырожденные числа — это снижает ложные срабатывания на
        числовых ID (номера заказов, артикулы), не трогая настоящие паспорта."""
        digits = re.sub(r"\D", "", value)
        if len(digits) != 10:
            return False
        if len(set(digits)) == 1:  # все цифры одинаковые (9999999999)
            return False
        if _is_sequential(digits):  # монотонная лесенка (1234567890)
            return False
        region, year = int(digits[:2]), int(digits[2:4])
        if not (_MIN_REGION <= region <= _MAX_REGION):
            return False
        current_2d = dt.date.today().year % 100
        if not (year in _LEGACY_YEARS_2D or 0 <= year <= current_2d + 1):
            return False
        return True
