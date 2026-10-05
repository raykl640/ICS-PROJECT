import { useEffect, useRef } from "react";
import { cx } from "../design/cx";
import { takePageFocus } from "./pageFocus";

/** The page's <h1>: sets the document title and takes focus after a navigation. */
export function PageTitle({
  children,
  hidden,
  large,
  className,
}: {
  children: string;
  hidden?: boolean;
  large?: boolean;
  className?: string;
}) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    document.title = `${children} — HakiAI`;
    if (takePageFocus()) ref.current?.focus();
  }, [children]);
  return (
    <h1
      ref={ref}
      tabIndex={-1}
      className={cx(
        hidden
          ? "sr-only"
          : large
            ? "font-display-style text-5xl text-ink sm:text-6xl lg:text-7xl"
            : "font-display-style text-4xl text-ink sm:text-5xl",
        "outline-none",
        className,
      )}
    >
      {children}
    </h1>
  );
}
