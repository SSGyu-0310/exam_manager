import {
    BookOpen,
    FileText,
    Home,
    LayoutGrid,
    Library,
    ListChecks,
    Settings,
    Sparkles,
    Upload,
} from "lucide-react";

export type NavItem = {
    label: string;
    key?: string;
    href: string;
    icon: React.ElementType;
    disabled?: boolean;
};

export type NavContext = "home" | "learn" | "review" | "manage";

export type TopNavItem = {
    label: string;
    key?: string;
    value: NavContext;
    href: string;
};

export const TOP_NAV: TopNavItem[] = [
    { label: "Home", key: "nav.home", value: "home", href: "/dashboard" },
    { label: "Learn", key: "nav.learn", value: "learn", href: "/learn" },
    { label: "Review", key: "nav.review", value: "review", href: "/review" },
    { label: "Manage", key: "nav.manage", value: "manage", href: "/manage" },
];

export const SIDEBAR_NAV: Record<NavContext, NavItem[]> = {
    home: [
        { label: "Dashboard", key: "sidebar.dashboard", href: "/dashboard", icon: Home },
        { label: "Recent Activity", key: "sidebar.recentActivity", href: "/dashboard/activity", icon: FileText },
    ],
    learn: [
        { label: "Practice Mode", key: "sidebar.practice", href: "/learn/practice", icon: BookOpen },
        { label: "Mock Exams", key: "sidebar.exams", href: "/learn/exams", icon: ListChecks },
        { label: "Recommendations", key: "sidebar.recommendations", href: "/learn/recommended", icon: Sparkles },
    ],
    review: [
        { label: "Weakness Analysis", key: "sidebar.weakness", href: "/review/weakness", icon: Sparkles },
        { label: "My Notes", key: "sidebar.notes", href: "/review/notes", icon: FileText },
        { label: "History", key: "sidebar.history", href: "/review/history", icon: Library },
    ],
    manage: [
        { label: "Blocks & Lectures", key: "sidebar.blockLectures", href: "/manage", icon: Library },
        { label: "Uploaded Exams", key: "sidebar.uploadedExams", href: "/manage/exams", icon: Upload },
        { label: "Classifications", key: "sidebar.classifications", href: "/manage/unclassified", icon: LayoutGrid },
        { label: "Settings", key: "common.settings", href: "/manage/settings", icon: Settings },
    ],
};
