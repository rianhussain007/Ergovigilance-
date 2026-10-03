import { useAuth } from '@/src/auth/AuthContext';
import {
  can,
  canCallEndpoint,
  capabilitiesFor,
  type Capability,
  type EndpointKey,
} from '@/src/auth/capabilities';

/** Can the signed-in role do `capability`? (single line, no role lists in pages) */
export function useCapability(capability: Capability): boolean {
  const { user } = useAuth();
  return can(user?.role, capability);
}

/**
 * Can the signed-in role call this endpoint?
 *
 * Use it for calls that sit inside a page a broader role set can open (e.g.
 * the nightly digest on /reports) so the page never fires a request the
 * backend will answer with 403.
 */
export function useEndpointAccess(endpoint: EndpointKey): boolean {
  const { user } = useAuth();
  return canCallEndpoint(user?.role, endpoint);
}

/** All capabilities for the signed-in role, plus a predicate. */
export function useCapabilities(): {
  can: (capability: Capability) => boolean;
  all: Capability[];
} {
  const { user } = useAuth();
  return {
    can: (capability: Capability) => can(user?.role, capability),
    all: capabilitiesFor(user?.role),
  };
}
