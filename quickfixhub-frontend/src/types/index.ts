// User types for DynamoDB integration
export type UserRole = 'homeowner' | 'provider' | 'admin';

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  phone?: string;
  address?: string;
  createdAt: string;
}

export interface ServiceProvider extends User {
  role: 'provider';
  specialties: ServiceType[];
  rating: number;
  completedJobs: number;
  available: boolean;
  bio?: string;
}

export type ServiceType = 'plumbing' | 'electrical' | 'carpentry' | 'painting' | 'cleaning' | 'hvac' | 'appliance' | 'general';

export type ServiceStatus = 'pending' |'offered'| 'accepted' | 'in_progress' | 'completed' | 'cancelled' | 'expired';

export interface ServiceRequest {
  id: string;
  userId: string;
  userName: string;
  userEmail: string;
  userPhone: string;
  serviceType: ServiceType;
  description: string;
  address: string;
  preferredDate: string;
  preferredTime: string;
  status: ServiceStatus;
  assignedProviderId?: string;
  providerName?: string;
  providerPhone?: string;
  providerEmail?: string;
  createdAt: string;
  updatedAt: string;
  estimatedCost?: number;
  notes?: string;
}

// Auth context types
export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

// API Response types (for Flask backend integration)
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
}
