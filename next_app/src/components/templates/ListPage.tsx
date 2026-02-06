import { cn } from "@/lib/utils";

interface ListPageProps {
    title: string;
    description?: string;
    children: React.ReactNode;
    /**
     * Primary actions displayed at the top right (e.g., "Create New", "Upload")
     */
    primaryAction?: React.ReactNode;
    /**
     * Secondary actions or filters displayed in the toolbar
     */
    toolbar?: React.ReactNode;
    className?: string;
}

export function ListPage({
    title,
    description,
    children,
    primaryAction,
    toolbar,
    className,
}: ListPageProps) {
    return (
        <div className={cn("flex flex-col gap-6", className)}>
            {/* Page Header */}
            <div className="flex flex-col gap-4 border-b border-border/60 pb-6 md:flex-row md:items-start md:justify-between">
                <div className="space-y-1">
                    <h2 className="text-2xl font-bold tracking-tight">{title}</h2>
                    {description && (
                        <p className="text-sm text-muted-foreground">{description}</p>
                    )}
                </div>
                {primaryAction && (
                    <div className="flex items-center gap-2">{primaryAction}</div>
                )}
            </div>

            {/* Toolbar / Filters */}
            {toolbar && (
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between rounded-lg border border-border/60 bg-card p-4 shadow-sm">
                    {toolbar}
                </div>
            )}

            {/* Main Content (List/Grid) */}
            <div className="min-h-[400px]">
                {children}
            </div>
        </div>
    );
}
