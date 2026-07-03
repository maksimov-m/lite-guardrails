// Иконка-перо (символ «lite» — лёгкий). Мягкое опахало + стержень-очин + бородки.
// Рисуется через currentColor — цвет наследуется от текста (адаптивно к теме:
// светлое перо на тёмном фоне, тёмное на светлом). Бородки тоньше контура
// (strokeWidth на самих path) и укорочены — сидят внутри опахала.
export default function FeatherIcon({ size = "1.15em", className = "", ...rest }) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      <path d="M17.8 5.5 C 9 4.3 5 9.4 5.9 14.8 C 6.6 18 10.3 19 13.4 17.1 C 16.2 15.4 18.1 10.5 17.8 5.5 Z" />
      <path d="M17.8 5.5 4.8 20.3" />
      <path strokeWidth="1.2" d="M9 10.2 C 10.6 11 12.2 11.2 13.8 10.7" />
      <path strokeWidth="1.2" d="M8.4 13 C 10 13.8 11.6 14 13.2 13.5" />
    </svg>
  );
}
