#!/usr/bin/env npx ts-node
/**
 * Set Super Admin Role Script
 *
 * Usage:
 *   npx ts-node scripts/set-super-admin.ts <user_email>
 *
 * Requires CLERK_SECRET_KEY in environment
 */

const CLERK_SECRET_KEY = process.env.CLERK_SECRET_KEY;

if (!CLERK_SECRET_KEY) {
  console.error('Error: CLERK_SECRET_KEY environment variable is required');
  console.error('Get it from: https://dashboard.clerk.com → API Keys');
  process.exit(1);
}

const email = process.argv[2];

if (!email) {
  console.error('Usage: npx ts-node scripts/set-super-admin.ts <user_email>');
  process.exit(1);
}

async function main() {
  // Find user by email
  const searchResponse = await fetch(
    `https://api.clerk.com/v1/users?email_address=${encodeURIComponent(email)}`,
    {
      headers: {
        Authorization: `Bearer ${CLERK_SECRET_KEY}`,
        'Content-Type': 'application/json',
      },
    }
  );

  if (!searchResponse.ok) {
    console.error('Failed to search users:', await searchResponse.text());
    process.exit(1);
  }

  const users = await searchResponse.json();

  if (users.length === 0) {
    console.error(`No user found with email: ${email}`);
    process.exit(1);
  }

  const user = users[0];
  console.log(`Found user: ${user.first_name} ${user.last_name} (${user.id})`);

  // Update public metadata
  const updateResponse = await fetch(
    `https://api.clerk.com/v1/users/${user.id}/metadata`,
    {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${CLERK_SECRET_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        public_metadata: {
          ...user.public_metadata,
          role: 'super_admin',
        },
      }),
    }
  );

  if (!updateResponse.ok) {
    console.error('Failed to update user:', await updateResponse.text());
    process.exit(1);
  }

  console.log('✅ Successfully set super_admin role!');
  console.log('   Refresh your browser to access /admin/knowledge');
}

main().catch(console.error);
