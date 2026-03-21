'use client';

import { LogOut, Menu, Bell, FileText, HelpCircle } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';

interface PortalHeaderProps {
  businessName: string;
  practiceName: string;
  pendingRequests?: number;
  onLogout?: () => void;
}

export function PortalHeader({
  businessName,
  practiceName,
  pendingRequests = 0,
  onLogout,
}: PortalHeaderProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems = [
    { href: '/portal', label: 'Dashboard', icon: FileText },
    { href: '/portal/requests', label: 'Requests', icon: FileText, badge: pendingRequests },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="container flex h-16 items-center justify-between px-4">
        {/* Logo and Practice Name */}
        <div className="flex items-center gap-4">
          <Link href="/portal" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground font-bold text-sm">
              C
            </div>
            <div className="hidden sm:block">
              <p className="text-sm font-semibold">{practiceName}</p>
              <p className="text-xs text-muted-foreground">Client Portal</p>
            </div>
          </Link>
        </div>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center gap-6">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              <item.icon className="h-4 w-4" />
              {item.label}
              {item.badge && item.badge > 0 && (
                <span className="inline-flex items-center justify-center h-5 min-w-5 px-1.5 text-xs font-medium bg-primary text-primary-foreground rounded-full">
                  {item.badge}
                </span>
              )}
            </Link>
          ))}
        </nav>

        {/* Right Side Actions */}
        <div className="flex items-center gap-2">
          {/* Notifications - Desktop */}
          <Button variant="ghost" size="icon" className="hidden md:inline-flex relative">
            <Bell className="h-4 w-4" />
            {pendingRequests > 0 && (
              <span className="absolute -top-0.5 -right-0.5 h-4 w-4 text-xs flex items-center justify-center bg-destructive text-destructive-foreground rounded-full">
                {pendingRequests}
              </span>
            )}
          </Button>

          {/* Help */}
          <Button variant="ghost" size="icon" className="hidden md:inline-flex">
            <HelpCircle className="h-4 w-4" />
          </Button>

          {/* User Menu - Desktop */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild className="hidden md:inline-flex">
              <Button variant="ghost" className="gap-2">
                <div className="h-7 w-7 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-medium">
                  {businessName.charAt(0).toUpperCase()}
                </div>
                <span className="hidden lg:inline text-sm">{businessName}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>
                <div className="flex flex-col">
                  <span className="font-medium">{businessName}</span>
                  <span className="text-xs text-muted-foreground">via {practiceName}</span>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link href="/portal/help">
                  <HelpCircle className="mr-2 h-4 w-4" />
                  Help & Support
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={onLogout} className="text-destructive">
                <LogOut className="mr-2 h-4 w-4" />
                Sign Out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Mobile Menu */}
          <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
            <SheetTrigger asChild className="md:hidden">
              <Button variant="ghost" size="icon">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-80">
              <div className="flex flex-col h-full">
                {/* Mobile Header */}
                <div className="flex items-center gap-3 pb-4 border-b">
                  <div className="h-10 w-10 rounded-full bg-primary/10 text-primary flex items-center justify-center text-lg font-medium">
                    {businessName.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <p className="font-medium">{businessName}</p>
                    <p className="text-sm text-muted-foreground">via {practiceName}</p>
                  </div>
                </div>

                {/* Mobile Navigation */}
                <nav className="flex-1 py-4 space-y-1">
                  {navItems.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileMenuOpen(false)}
                      className={cn(
                        "flex items-center justify-between px-3 py-2 rounded-md text-sm font-medium",
                        "text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <item.icon className="h-4 w-4" />
                        {item.label}
                      </div>
                      {item.badge && item.badge > 0 && (
                        <span className="inline-flex items-center justify-center h-5 min-w-5 px-1.5 text-xs font-medium bg-primary text-primary-foreground rounded-full">
                          {item.badge}
                        </span>
                      )}
                    </Link>
                  ))}
                </nav>

                {/* Mobile Footer */}
                <div className="border-t pt-4 space-y-2">
                  <Link
                    href="/portal/help"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex items-center gap-3 px-3 py-2 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  >
                    <HelpCircle className="h-4 w-4" />
                    Help & Support
                  </Link>
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setMobileMenuOpen(false);
                      onLogout?.();
                    }}
                    className="w-full justify-start gap-3 px-3 text-destructive hover:text-destructive hover:bg-destructive/10"
                  >
                    <LogOut className="h-4 w-4" />
                    Sign Out
                  </Button>
                </div>
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}

export default PortalHeader;
