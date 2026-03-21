/**
 * Biometric Authentication Hook
 *
 * Provides WebAuthn biometric authentication functionality.
 *
 * Spec: 032-pwa-mobile-document-capture
 */

import { useState, useCallback, useEffect } from 'react';

import { portalApi } from '@/lib/api/portal';

// =============================================================================
// Types
// =============================================================================

export interface BiometricCredential {
  id: string;
  device_name: string | null;
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface BiometricStatus {
  isSupported: boolean;
  hasCredentials: boolean;
  credentialCount: number;
}

export interface UseBiometricAuthReturn {
  /** Current biometric status */
  status: BiometricStatus;
  /** Whether biometric is loading */
  isLoading: boolean;
  /** List of registered credentials */
  credentials: BiometricCredential[];
  /** Error message if any */
  error: string | null;
  /** Register a new biometric credential */
  register: (deviceName?: string) => Promise<BiometricCredential>;
  /** Authenticate with biometric */
  authenticate: () => Promise<boolean>;
  /** Delete a credential */
  deleteCredential: (credentialId: string) => Promise<void>;
  /** Refresh status and credentials */
  refresh: () => Promise<void>;
}

// =============================================================================
// WebAuthn Support Detection
// =============================================================================

/**
 * Check if WebAuthn is supported in the browser.
 */
export function isWebAuthnSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.PublicKeyCredential !== undefined &&
    typeof window.PublicKeyCredential === 'function'
  );
}

/**
 * Check if platform authenticator (biometric) is available.
 */
export async function isPlatformAuthenticatorAvailable(): Promise<boolean> {
  if (!isWebAuthnSupported()) return false;

  try {
    return await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
  } catch {
    return false;
  }
}

// =============================================================================
// Base64URL Helpers
// =============================================================================

function base64UrlEncode(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  const str = Array.from(bytes, (byte) => String.fromCharCode(byte)).join('');
  return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

function base64UrlDecode(str: string): ArrayBuffer {
  // Add padding
  const padding = 4 - (str.length % 4);
  if (padding !== 4) {
    str += '='.repeat(padding);
  }
  // Convert base64url to base64
  str = str.replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(str);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

// =============================================================================
// Hook
// =============================================================================

export function useBiometricAuth(): UseBiometricAuthReturn {
  const [status, setStatus] = useState<BiometricStatus>({
    isSupported: false,
    hasCredentials: false,
    credentialCount: 0,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [credentials, setCredentials] = useState<BiometricCredential[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Check support and load status on mount
  useEffect(() => {
    let mounted = true;

    const init = async () => {
      // Check browser support
      const supported = await isPlatformAuthenticatorAvailable();

      if (!supported) {
        if (mounted) {
          setStatus({
            isSupported: false,
            hasCredentials: false,
            credentialCount: 0,
          });
          setIsLoading(false);
        }
        return;
      }

      // Load status from API
      try {
        const response = await portalApi.push.getBiometricStatus();
        if (mounted) {
          setStatus({
            isSupported: true,
            hasCredentials: response.has_credentials,
            credentialCount: response.credential_count,
          });

          if (response.has_credentials) {
            const credsResponse = await portalApi.push.listBiometricCredentials();
            if (mounted) {
              setCredentials(credsResponse.credentials);
            }
          }
        }
      } catch (err) {
        console.error('[Biometric] Failed to load status:', err);
        if (mounted) {
          setStatus({
            isSupported: true,
            hasCredentials: false,
            credentialCount: 0,
          });
        }
      } finally {
        if (mounted) {
          setIsLoading(false);
        }
      }
    };

    init();

    return () => {
      mounted = false;
    };
  }, []);

  // Refresh status and credentials
  const refresh = useCallback(async () => {
    if (!status.isSupported) return;

    try {
      const response = await portalApi.push.getBiometricStatus();
      setStatus((prev) => ({
        ...prev,
        hasCredentials: response.has_credentials,
        credentialCount: response.credential_count,
      }));

      if (response.has_credentials) {
        const credsResponse = await portalApi.push.listBiometricCredentials();
        setCredentials(credsResponse.credentials);
      } else {
        setCredentials([]);
      }

      setError(null);
    } catch (err) {
      console.error('[Biometric] Failed to refresh:', err);
      setError('Failed to load biometric status');
    }
  }, [status.isSupported]);

  // Register a new biometric credential
  const register = useCallback(
    async (deviceName?: string): Promise<BiometricCredential> => {
      if (!status.isSupported) {
        throw new Error('Biometric authentication not supported');
      }

      setError(null);

      try {
        // Get registration options from server
        const options = await portalApi.push.getWebAuthnRegistrationOptions();

        // Prepare options for navigator.credentials.create()
        const publicKeyOptions: PublicKeyCredentialCreationOptions = {
          challenge: base64UrlDecode(options.challenge),
          rp: {
            id: options.rp.id,
            name: options.rp.name,
          },
          user: {
            id: base64UrlDecode(options.user.id),
            name: options.user.name,
            displayName: options.user.displayName,
          },
          pubKeyCredParams: options.pub_key_cred_params.map((param) => ({
            type: param.type as PublicKeyCredentialType,
            alg: param.alg,
          })),
          timeout: options.timeout,
          authenticatorSelection: {
            authenticatorAttachment:
              options.authenticator_selection?.authenticatorAttachment as AuthenticatorAttachment | undefined,
            userVerification:
              (options.authenticator_selection?.userVerification as UserVerificationRequirement) ??
              'preferred',
            residentKey:
              (options.authenticator_selection?.residentKey as ResidentKeyRequirement) ??
              'preferred',
          },
          attestation: options.attestation as AttestationConveyancePreference,
        };

        // Create credential
        const credential = (await navigator.credentials.create({
          publicKey: publicKeyOptions,
        })) as PublicKeyCredential;

        if (!credential) {
          throw new Error('Failed to create credential');
        }

        const attestationResponse = credential.response as AuthenticatorAttestationResponse;

        // Send to server for verification
        const credentialResponse = {
          id: credential.id,
          rawId: base64UrlEncode(credential.rawId),
          type: credential.type,
          response: {
            clientDataJSON: base64UrlEncode(attestationResponse.clientDataJSON),
            attestationObject: base64UrlEncode(attestationResponse.attestationObject),
          },
        };

        const result = await portalApi.push.verifyWebAuthnRegistration(
          credentialResponse,
          deviceName
        );

        // Refresh credentials list
        await refresh();

        return result;
      } catch (err: unknown) {
        console.error('[Biometric] Registration failed:', err);

        if (err instanceof Error) {
          if (err.name === 'NotAllowedError') {
            setError('Biometric registration was cancelled');
          } else if (err.name === 'InvalidStateError') {
            setError('A biometric credential already exists for this device');
          } else {
            setError(err.message || 'Failed to register biometric');
          }
          throw err;
        }

        setError('Failed to register biometric');
        throw new Error('Failed to register biometric');
      }
    },
    [status.isSupported, refresh]
  );

  // Authenticate with biometric
  const authenticate = useCallback(async (): Promise<boolean> => {
    if (!status.isSupported || !status.hasCredentials) {
      throw new Error('No biometric credentials registered');
    }

    setError(null);

    try {
      // Get authentication options from server
      const options = await portalApi.push.getWebAuthnAuthenticationOptions();

      // Prepare options for navigator.credentials.get()
      const publicKeyOptions: PublicKeyCredentialRequestOptions = {
        challenge: base64UrlDecode(options.challenge),
        timeout: options.timeout,
        rpId: options.rp_id,
        allowCredentials: options.allow_credentials.map((cred) => ({
          id: base64UrlDecode(cred.id),
          type: cred.type as PublicKeyCredentialType,
          transports: cred.transports as AuthenticatorTransport[] | undefined,
        })),
        userVerification: options.user_verification as UserVerificationRequirement,
      };

      // Get credential
      const credential = (await navigator.credentials.get({
        publicKey: publicKeyOptions,
      })) as PublicKeyCredential;

      if (!credential) {
        throw new Error('Authentication failed');
      }

      const assertionResponse = credential.response as AuthenticatorAssertionResponse;

      // Send to server for verification
      const assertionData = {
        id: credential.id,
        rawId: base64UrlEncode(credential.rawId),
        type: credential.type,
        response: {
          clientDataJSON: base64UrlEncode(assertionResponse.clientDataJSON),
          authenticatorData: base64UrlEncode(assertionResponse.authenticatorData),
          signature: base64UrlEncode(assertionResponse.signature),
          userHandle: assertionResponse.userHandle
            ? base64UrlEncode(assertionResponse.userHandle)
            : undefined,
        },
      };

      const result = await portalApi.push.verifyWebAuthnAuthentication(assertionData);
      return result.authenticated;
    } catch (err: unknown) {
      console.error('[Biometric] Authentication failed:', err);

      if (err instanceof Error) {
        if (err.name === 'NotAllowedError') {
          setError('Authentication was cancelled');
        } else {
          setError(err.message || 'Authentication failed');
        }
        throw err;
      }

      setError('Authentication failed');
      throw new Error('Authentication failed');
    }
  }, [status.isSupported, status.hasCredentials]);

  // Delete a credential
  const deleteCredential = useCallback(
    async (credentialId: string) => {
      try {
        await portalApi.push.deleteBiometricCredential(credentialId);
        await refresh();
        setError(null);
      } catch (err) {
        console.error('[Biometric] Failed to delete credential:', err);
        setError('Failed to delete credential');
        throw err;
      }
    },
    [refresh]
  );

  return {
    status,
    isLoading,
    credentials,
    error,
    register,
    authenticate,
    deleteCredential,
    refresh,
  };
}
