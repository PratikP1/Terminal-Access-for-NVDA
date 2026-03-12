//! Security: named pipe DACL and HWND validation.
//!
//! - Pipe DACL restricts access to the current user's SID only.
//! - HWND validation checks the window exists before UIA operations.

use std::io;
use std::mem;
use std::ptr;

use windows::Win32::Foundation::*;
use windows::Win32::Security::Authorization::*;
use windows::Win32::Security::*;
use windows::Win32::System::Threading::*;
use windows::Win32::UI::WindowsAndMessaging::*;

// Windows constants not exposed in windows crate 0.58
const GENERIC_READ: u32 = 0x80000000;
const GENERIC_WRITE: u32 = 0x40000000;

/// Create a `SECURITY_ATTRIBUTES` with a DACL that grants access only
/// to the current user.  The returned struct (and the ACL it points to)
/// must be kept alive while the pipe handle is open.
pub struct PipeSecurity {
    _sd_buf: Vec<u8>,
    _acl: *mut ACL,
    pub attrs: SECURITY_ATTRIBUTES,
}

// The struct is only used from the thread that creates the pipe.
unsafe impl Send for PipeSecurity {}

impl PipeSecurity {
    /// Build a security descriptor restricted to the current user.
    pub fn new() -> io::Result<Self> {
        unsafe {
            // 1. Get current process token
            let mut token = HANDLE::default();
            OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut token)
                .map_err(|e| io::Error::new(io::ErrorKind::PermissionDenied, e.to_string()))?;

            // 2. Get token user info (contains the SID)
            let mut info_len: u32 = 0;
            let _ = GetTokenInformation(token, TokenUser, None, 0, &mut info_len);
            let mut info_buf = vec![0u8; info_len as usize];
            GetTokenInformation(
                token,
                TokenUser,
                Some(info_buf.as_mut_ptr().cast()),
                info_len,
                &mut info_len,
            )
            .map_err(|e| io::Error::new(io::ErrorKind::PermissionDenied, e.to_string()))?;

            let _ = CloseHandle(token);

            let token_user: &TOKEN_USER = &*(info_buf.as_ptr() as *const TOKEN_USER);
            let user_sid = token_user.User.Sid;

            // 3. Build an explicit access entry for the current user
            let ea = EXPLICIT_ACCESS_W {
                grfAccessPermissions: GENERIC_READ | GENERIC_WRITE,
                grfAccessMode: SET_ACCESS,
                grfInheritance: NO_INHERITANCE,
                Trustee: TRUSTEE_W {
                    TrusteeForm: TRUSTEE_IS_SID,
                    TrusteeType: TRUSTEE_IS_USER,
                    ptstrName: windows::core::PWSTR(user_sid.0 as *mut u16),
                    ..Default::default()
                },
            };

            // 4. Create ACL from the explicit access entry
            let mut acl: *mut ACL = ptr::null_mut();
            let result = SetEntriesInAclW(Some(&[ea]), None, &mut acl);
            if result.0 != 0 {
                return Err(io::Error::new(
                    io::ErrorKind::PermissionDenied,
                    format!("SetEntriesInAclW failed: error {}", result.0),
                ));
            }

            // 5. Create security descriptor
            let mut sd_buf = vec![0u8; mem::size_of::<SECURITY_DESCRIPTOR>()];
            let sd = sd_buf.as_mut_ptr() as *mut SECURITY_DESCRIPTOR;
            // SECURITY_DESCRIPTOR_REVISION = 1
            InitializeSecurityDescriptor(PSECURITY_DESCRIPTOR(sd.cast()), 1u32)
                .map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))?;

            SetSecurityDescriptorDacl(PSECURITY_DESCRIPTOR(sd.cast()), true, Some(acl), false)
                .map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))?;

            // 6. Build SECURITY_ATTRIBUTES
            let attrs = SECURITY_ATTRIBUTES {
                nLength: mem::size_of::<SECURITY_ATTRIBUTES>() as u32,
                lpSecurityDescriptor: sd.cast(),
                bInheritHandle: FALSE,
            };

            Ok(PipeSecurity {
                _sd_buf: sd_buf,
                _acl: acl,
                attrs,
            })
        }
    }
}

impl Drop for PipeSecurity {
    fn drop(&mut self) {
        if !self._acl.is_null() {
            // ACL was allocated by SetEntriesInAclW via LocalAlloc;
            // free it with LocalFree from kernel32.
            unsafe {
                #[link(name = "kernel32")]
                extern "system" {
                    fn LocalFree(hMem: *mut core::ffi::c_void) -> *mut core::ffi::c_void;
                }
                LocalFree(self._acl as *mut _);
            }
            self._acl = ptr::null_mut();
        }
    }
}

/// Validate that an HWND refers to a real, existing window.
pub fn validate_hwnd(hwnd: isize) -> io::Result<()> {
    if hwnd == 0 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "HWND is zero",
        ));
    }

    let wnd = HWND(hwnd as *mut _);
    unsafe {
        if !IsWindow(wnd).as_bool() {
            return Err(io::Error::new(
                io::ErrorKind::NotFound,
                format!("HWND {hwnd} is not a valid window"),
            ));
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pipe_security_creation() {
        // Should succeed on Windows
        let sec = PipeSecurity::new();
        assert!(sec.is_ok(), "PipeSecurity::new() failed: {:?}", sec.err());
    }

    #[test]
    fn test_validate_hwnd_zero() {
        assert!(validate_hwnd(0).is_err());
    }

    #[test]
    fn test_validate_hwnd_invalid() {
        // Very unlikely to be a valid window handle
        assert!(validate_hwnd(0x7FFFFFFF).is_err());
    }

    #[test]
    fn test_validate_hwnd_desktop() {
        // The desktop window should always be valid
        let desktop = unsafe { GetDesktopWindow() };
        assert!(validate_hwnd(desktop.0 as isize).is_ok());
    }
}
