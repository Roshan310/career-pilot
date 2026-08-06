import {
  BarChart3,
  Briefcase,
  Clock,
  FileSearch,
  FolderClosed,
  LayoutDashboard,
  Mic,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /** Shown in the nav but not yet built. */
  comingSoon?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Resume Analysis", href: "/analysis", icon: FileSearch },
  { label: "Resume Library", href: "/resumes", icon: FolderClosed },
  { label: "Job Descriptions", href: "/jobs", icon: Briefcase },
  { label: "Interview Practice", href: "/interview", icon: Mic },
  { label: "Interview History", href: "/interviews", icon: Clock },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Settings", href: "/settings", icon: Settings },
];
