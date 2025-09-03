import { apiService } from './api';

class AuthService {
  async login(credentials) {
    try {
      const response = await apiService.login(credentials);
      return {
        token: response.access_token,
        user: response.user
      };
    } catch (error) {
      throw new Error(error.message || 'Login failed');
    }
  }

  async validateToken(token) {
    try {
      const response = await apiService.validateToken();
      return response;
    } catch (error) {
      throw new Error('Token validation failed');
    }
  }

  logout() {
    localStorage.removeItem('veritas_token');
    window.location.href = '/';
  }

  isAuthenticated() {
    return !!localStorage.getItem('veritas_token');
  }

  getToken() {
    return localStorage.getItem('veritas_token');
  }
}

export const authService = new AuthService();