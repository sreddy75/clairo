'use client';

/**
 * Invite to Portal Modal
 *
 * Allows accountants to invite a client business owner to the portal
 * by generating a magic link.
 */

import { zodResolver } from '@hookform/resolvers/zod';
import { Check, Copy, Loader2, Mail, Send, UserPlus } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import * as z from 'zod';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { useToast } from '@/hooks/use-toast';
import { usePortalApi } from '@/lib/api/requests';

const formSchema = z.object({
  email: z.string().email('Please enter a valid email address'),
});

type FormValues = z.infer<typeof formSchema>;

interface InviteToPortalModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connectionId: string;
  clientName: string;
  defaultEmail?: string;
}

export function InviteToPortalModal({
  open,
  onOpenChange,
  connectionId,
  clientName,
  defaultEmail = '',
}: InviteToPortalModalProps) {
  const api = usePortalApi();
  const { toast } = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [magicLink, setMagicLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: defaultEmail,
    },
  });

  const handleSubmit = async (values: FormValues) => {
    setIsSubmitting(true);
    setMagicLink(null);

    try {
      const result = await api.createInvitation(connectionId, values.email);
      setMagicLink(result.magic_link_url);

      toast({
        title: 'Invitation created',
        description: `Portal access invitation sent to ${values.email}`,
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to create invitation',
        variant: 'destructive',
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopy = async () => {
    if (!magicLink) return;

    try {
      await navigator.clipboard.writeText(magicLink);
      setCopied(true);
      toast({
        title: 'Copied!',
        description: 'Magic link copied to clipboard',
      });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast({
        title: 'Failed to copy',
        description: 'Please copy the link manually',
        variant: 'destructive',
      });
    }
  };

  const handleClose = () => {
    setMagicLink(null);
    setCopied(false);
    form.reset({ email: defaultEmail });
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UserPlus className="h-5 w-5" />
            Invite to Portal
          </DialogTitle>
          <DialogDescription>
            Send a magic link to give <strong>{clientName}</strong> access to view and respond to
            document requests.
          </DialogDescription>
        </DialogHeader>

        {!magicLink ? (
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email Address</FormLabel>
                    <FormControl>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                          type="email"
                          placeholder="client@example.com"
                          className="pl-9"
                          {...field}
                        />
                      </div>
                    </FormControl>
                    <FormDescription>
                      The business owner will receive a secure link to access their portal
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <DialogFooter>
                <Button type="button" variant="outline" onClick={handleClose}>
                  Cancel
                </Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <Send className="h-4 w-4 mr-2" />
                  )}
                  Send Invitation
                </Button>
              </DialogFooter>
            </form>
          </Form>
        ) : (
          <div className="space-y-4">
            <div className="rounded-lg bg-status-success/10 p-4 border border-status-success/20">
              <div className="flex items-center gap-2 text-status-success mb-2">
                <Check className="h-5 w-5" />
                <span className="font-medium">Invitation Created!</span>
              </div>
              <p className="text-sm text-status-success">
                Share this magic link with your client. It will expire in 7 days.
              </p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Magic Link</label>
              <div className="flex gap-2">
                <Input
                  readOnly
                  value={magicLink}
                  className="font-mono text-xs"
                  onClick={(e) => e.currentTarget.select()}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={handleCopy}
                  className="flex-shrink-0"
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-status-success" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                The client can use this link to securely access their portal without a password.
              </p>
            </div>

            <DialogFooter>
              <Button type="button" onClick={handleClose}>
                Done
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default InviteToPortalModal;
