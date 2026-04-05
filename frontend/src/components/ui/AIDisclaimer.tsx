import { Info } from "lucide-react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { AI_DISCLAIMER_TEXT } from "@/lib/constants";
import { cn } from "@/lib/utils";

interface AIDisclaimerProps {
  className?: string;
}

export function AIDisclaimer({ className }: AIDisclaimerProps) {
  return (
    <Alert variant="default" className={cn("bg-muted/50", className)}>
      <Info className="h-4 w-4" />
      <AlertDescription className="text-xs text-muted-foreground">
        {AI_DISCLAIMER_TEXT}
      </AlertDescription>
    </Alert>
  );
}
