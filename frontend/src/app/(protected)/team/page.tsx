'use client';

/**
 * Team Page
 *
 * Lists active team members and pending invitations with management actions.
 * Admins can invite new members, change roles, and manage invitations.
 */

import { useAuth, useUser } from '@clerk/nextjs';
import {
  Clock,
  Loader2,
  Plus,
  Shield,
  ShieldCheck,
  Trash2,
  User,
  UserPlus,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { TenantUser } from '@/lib/api/users';
import { listTenantUsers } from '@/lib/api/users';
import { apiClient } from '@/lib/api-client';
import { formatRelativeTime } from '@/lib/formatters';

// ─── Types ──────────────────────────────────────────────────────────────────

type RoleKey = 'admin' | 'accountant' | 'staff';

interface Invitation {
  id: string;
  email: string;
  role: RoleKey;
  status: 'pending' | 'accepted' | 'expired' | 'revoked';
  expires_at: string;
  created_at: string;
}

// ─── Role Config ────────────────────────────────────────────────────────────

const ROLE_CONFIG: Record<RoleKey, { label: string; variant: 'default' | 'secondary' | 'outline'; icon: React.ComponentType<{ className?: string }> }> = {
  admin: { label: 'Admin', variant: 'default', icon: ShieldCheck },
  accountant: { label: 'Accountant', variant: 'secondary', icon: Shield },
  staff: { label: 'Staff', variant: 'outline', icon: User },
};

const ROLES: { value: RoleKey; label: string; description: string }[] = [
  { value: 'admin', label: 'Admin', description: 'Full access + user management' },
  { value: 'accountant', label: 'Accountant', description: 'Client & BAS operations' },
  { value: 'staff', label: 'Staff', description: 'Read-only access' },
];

// ─── Page ───────────────────────────────────────────────────────────────────

export default function TeamPage() {
  const { getToken } = useAuth();
  const { user } = useUser();
  const userRole = user?.publicMetadata?.role as string | undefined;
  const isAdmin = userRole === 'admin' || userRole === 'super_admin';

  const [users, setUsers] = useState<TenantUser[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<RoleKey>('accountant');
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [inviteSuccess, setInviteSuccess] = useState(false);
  const [updatingRole, setUpdatingRole] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const token = await getToken();
      if (!token) return;

      const [usersResult, invitationsResponse] = await Promise.all([
        listTenantUsers(token),
        apiClient.get('/api/v1/auth/invitations?pending_only=true', {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      setUsers(usersResult.users.filter((u) => u.is_active));

      if (invitationsResponse.ok) {
        const invData = await invitationsResponse.json();
        setInvitations(invData.invitations ?? []);
      }
    } catch {
      // silently handle
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ─── Invite ─────────────────────────────────────────────────────────────

  const handleInvite = async () => {
    if (!inviteEmail.trim()) return;
    setInviting(true);
    setInviteError(null);
    setInviteSuccess(false);

    try {
      const token = await getToken();
      if (!token) return;
      const response = await apiClient.post('/api/v1/auth/invitations', {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: inviteEmail.trim(), role: inviteRole }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        const msg = data?.detail?.error?.message || data?.detail || `Failed to send invite (${response.status})`;
        throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
      }

      setInviteSuccess(true);
      setInviteEmail('');
      setInviteRole('accountant');
      setTimeout(() => {
        setInviteOpen(false);
        setInviteSuccess(false);
        fetchData();
      }, 1000);
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : 'Failed to send invite');
    } finally {
      setInviting(false);
    }
  };

  // ─── Revoke Invitation ──────────────────────────────────────────────────

  const handleRevoke = async (invitationId: string) => {
    setActionLoading(invitationId);
    try {
      const token = await getToken();
      if (!token) return;
      await apiClient.post(`/api/v1/auth/invitations/${invitationId}/revoke`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      await fetchData();
    } catch {
      // Could add toast
    } finally {
      setActionLoading(null);
    }
  };

  // ─── Resend Invitation ──────────────────────────────────────────────────

  const handleResend = async (invitation: Invitation) => {
    setActionLoading(invitation.id);
    try {
      const token = await getToken();
      if (!token) return;

      // Revoke old invitation first
      await apiClient.post(`/api/v1/auth/invitations/${invitation.id}/revoke`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      // Create new invitation with same email and role
      await apiClient.post('/api/v1/auth/invitations', {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: invitation.email, role: invitation.role }),
      });

      await fetchData();
    } catch {
      // Could add toast
    } finally {
      setActionLoading(null);
    }
  };

  // ─── Role Change ────────────────────────────────────────────────────────

  const handleRoleChange = async (userId: string, newRole: RoleKey) => {
    setUpdatingRole(userId);
    try {
      const token = await getToken();
      if (!token) return;
      const response = await apiClient.patch(`/api/v1/auth/users/${userId}/role`, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: newRole }),
      });

      if (!response.ok) return;
      await fetchData();
    } catch {
      // Could add toast
    } finally {
      setUpdatingRole(null);
    }
  };

  // ─── Stats ──────────────────────────────────────────────────────────────

  const adminCount = users.filter((u) => u.role === 'admin').length;
  const accountantCount = users.filter((u) => u.role === 'accountant').length;
  const staffCount = users.filter((u) => u.role === 'staff').length;
  const pendingCount = invitations.filter((i) => i.status === 'pending').length;

  // ─── Render ─────────────────────────────────────────────────────────────

  if (user && !isAdmin) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        <p>You don&apos;t have permission to view this page.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Team</h1>
          <p className="text-sm text-muted-foreground">
            Practice team members and their roles
          </p>
        </div>
        <Button onClick={() => setInviteOpen(true)}>
          <UserPlus className="mr-2 h-4 w-4" />
          Invite Member
        </Button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Total Members</p>
            <p className="text-2xl font-semibold tabular-nums">{users.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Accountants</p>
            <p className="text-2xl font-semibold tabular-nums">{accountantCount + adminCount}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Staff</p>
            <p className="text-2xl font-semibold tabular-nums">{staffCount}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Pending Invites</p>
            <p className="text-2xl font-semibold tabular-nums">{pendingCount}</p>
          </CardContent>
        </Card>
      </div>

      {/* Active Members Table */}
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : users.length === 0 && invitations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <User className="h-10 w-10 mb-3 opacity-40" />
              <p className="text-sm">No team members yet</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={() => setInviteOpen(true)}
              >
                <Plus className="mr-1.5 h-3.5 w-3.5" />
                Invite your first team member
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Member</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Login</TableHead>
                  <TableHead className="w-[100px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* Active users */}
                {users.map((user) => {
                  const roleConfig = (ROLE_CONFIG[user.role] ?? ROLE_CONFIG['staff'])!;
                  const RoleIcon = roleConfig.icon;
                  const isUpdating = updatingRole === user.id;

                  return (
                    <TableRow key={user.id}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted">
                            <RoleIcon className="h-4 w-4 text-muted-foreground" />
                          </div>
                          <p className="font-medium">{user.email}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Select
                          value={user.role}
                          onValueChange={(value) => handleRoleChange(user.id, value as RoleKey)}
                          disabled={isUpdating}
                        >
                          <SelectTrigger className="w-[140px] h-8">
                            {isUpdating ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <SelectValue>
                                {ROLE_CONFIG[user.role]?.label ?? user.role}
                              </SelectValue>
                            )}
                          </SelectTrigger>
                          <SelectContent>
                            {ROLES.map((role) => (
                              <SelectItem key={role.value} value={role.value}>
                                <span className="font-medium">{role.label}</span>
                                <span className="ml-2 text-xs text-muted-foreground">
                                  {role.description}
                                </span>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="border-emerald-300 text-emerald-700">
                          Active
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {user.last_login_at
                          ? formatRelativeTime(user.last_login_at)
                          : 'Never'}
                      </TableCell>
                      <TableCell />
                    </TableRow>
                  );
                })}

                {/* Pending invitations */}
                {invitations.filter((i) => i.status === 'pending').map((inv) => {
                  const roleConfig = (ROLE_CONFIG[inv.role] ?? ROLE_CONFIG['staff'])!;
                  const isActioning = actionLoading === inv.id;

                  return (
                    <TableRow key={inv.id} className="bg-muted/30">
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted">
                            <Clock className="h-4 w-4 text-muted-foreground" />
                          </div>
                          <div>
                            <p className="font-medium">{inv.email}</p>
                            <p className="text-xs text-muted-foreground">
                              Invited {formatRelativeTime(inv.created_at)}
                            </p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={roleConfig.variant}>
                          {roleConfig.label}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="border-blue-300 text-blue-700">
                          Invited
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        Expires {formatRelativeTime(inv.expires_at)}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 px-2 text-xs"
                            disabled={isActioning}
                            onClick={() => handleResend(inv)}
                          >
                            {isActioning ? (
                              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <UserPlus className="mr-1 h-3.5 w-3.5" />
                            )}
                            Reinvite
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-red-600 hover:text-red-700 hover:bg-red-50"
                            title="Revoke invitation"
                            disabled={isActioning}
                            onClick={() => handleRevoke(inv.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Invite Dialog */}
      <Dialog open={inviteOpen} onOpenChange={(open) => {
        setInviteOpen(open);
        if (!open) {
          setInviteError(null);
          setInviteSuccess(false);
        }
      }}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Invite Team Member</DialogTitle>
            <DialogDescription>
              Send an invitation email to add a new team member to your practice.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="invite-email">Email address</Label>
              <Input
                id="invite-email"
                type="email"
                placeholder="colleague@firm.com.au"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleInvite()}
                disabled={inviting}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="invite-role">Role</Label>
              <Select
                value={inviteRole}
                onValueChange={(value) => setInviteRole(value as RoleKey)}
                disabled={inviting}
              >
                <SelectTrigger id="invite-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((role) => (
                    <SelectItem key={role.value} value={role.value}>
                      <span className="font-medium">{role.label}</span>
                      <span className="ml-2 text-xs text-muted-foreground">
                        — {role.description}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {inviteError && (
              <p className="text-sm text-red-600">{inviteError}</p>
            )}
            {inviteSuccess && (
              <p className="text-sm text-emerald-600">Invitation sent!</p>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setInviteOpen(false)}
              disabled={inviting}
            >
              Cancel
            </Button>
            <Button
              onClick={handleInvite}
              disabled={inviting || !inviteEmail.trim()}
            >
              {inviting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <UserPlus className="mr-2 h-4 w-4" />
              )}
              Send Invite
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
