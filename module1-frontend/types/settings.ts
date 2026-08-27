export interface UpdateProfileRequest {
  full_name: string
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

export interface ChangePasswordResponse {
  message: string
}
