"use client";

import * as React from "react";
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { AppRouterCacheProvider } from "@mui/material-nextjs/v16-appRouter";

const paletteTokens = {
  primary: "#1b3c52",
  onPrimary: "#fdfbf7",
  secondary: "#f2c57c",
  onSecondary: "#2b1d0f",
  danger: "#b83a3a",
  warning: "#c57b1e",
  success: "#1f7a5b",
  background: "#f6f1e9",
  surface: "#ffffff",
  text: "#1a1a1a",
  textMuted: "#5c5c5c",
};

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: paletteTokens.primary,
      contrastText: paletteTokens.onPrimary,
    },
    secondary: {
      main: paletteTokens.secondary,
      contrastText: paletteTokens.onSecondary,
    },
    error: {
      main: paletteTokens.danger,
    },
    warning: {
      main: paletteTokens.warning,
    },
    success: {
      main: paletteTokens.success,
    },
    background: {
      default: paletteTokens.background,
      paper: paletteTokens.surface,
    },
    text: {
      primary: paletteTokens.text,
      secondary: paletteTokens.textMuted,
    },
  },
  shape: {
    borderRadius: 12,
  },
  typography: {
    fontFamily: "var(--font-sans)",
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: "var(--radius-md)",
          textTransform: "none",
          fontWeight: 600,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-1)",
        },
      },
    },
  },
});

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <AppRouterCacheProvider options={{ key: "mui" }}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </AppRouterCacheProvider>
  );
}
