"use client";

import * as React from "react";

const Collapsible = ({
    children,
    open,
    onOpenChange,
}: {
    children: React.ReactNode;
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
}) => {
    const [isOpen, setIsOpen] = React.useState(open ?? false);

    React.useEffect(() => {
        if (open !== undefined) setIsOpen(open);
    }, [open]);

    const handleToggle = () => {
        const newState = !isOpen;
        setIsOpen(newState);
        onOpenChange?.(newState);
    };

    return (
        <div data-state={isOpen ? "open" : "closed"}>
            {React.Children.map(children, (child) => {
                if (React.isValidElement(child)) {
                    if (child.type === CollapsibleTrigger) {
                        return React.cloneElement(child as React.ReactElement<{ onClick: () => void }>, {
                            onClick: handleToggle,
                        });
                    }
                    if (child.type === CollapsibleContent) {
                        return isOpen ? child : null;
                    }
                }
                return child;
            })}
        </div>
    );
};

const CollapsibleTrigger = ({
    children,
    asChild,
    onClick,
}: {
    children: React.ReactNode;
    asChild?: boolean;
    onClick?: () => void;
}) => {
    if (asChild && React.isValidElement(children)) {
        return React.cloneElement(children as React.ReactElement<{ onClick: () => void }>, {
            onClick,
        });
    }
    return <div onClick={onClick}>{children}</div>;
};

const CollapsibleContent = ({ children, className }: { children: React.ReactNode; className?: string }) => {
    return <div className={className}>{children}</div>;
};

export { Collapsible, CollapsibleTrigger, CollapsibleContent };
