/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";

export type TMermaidTheme = "dark" | "neutral";

function isDarkThemeValue(themeValue: string | null): boolean {
  if (!themeValue) {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  return themeValue.includes("dark");
}

export function resolveMermaidTheme(themeValue?: string | null): TMermaidTheme {
  return isDarkThemeValue(themeValue ?? document.documentElement.getAttribute("data-theme")) ? "dark" : "neutral";
}

export function useEditorTheme(): TMermaidTheme {
  const [theme, setTheme] = useState<TMermaidTheme>(() => resolveMermaidTheme());

  useEffect(() => {
    const updateTheme = () => {
      setTheme(resolveMermaidTheme());
    };

    updateTheme();

    const observer = new MutationObserver(updateTheme);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme", "class"],
    });

    const colorSchemeQuery = window.matchMedia("(prefers-color-scheme: dark)");
    colorSchemeQuery.addEventListener("change", updateTheme);

    return () => {
      observer.disconnect();
      colorSchemeQuery.removeEventListener("change", updateTheme);
    };
  }, []);

  return theme;
}
