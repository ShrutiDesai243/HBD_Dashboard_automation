import {
  Input,
  Checkbox,
  Button,
  Typography,
  Dialog,
  DialogHeader,
  DialogBody,
  DialogFooter,
} from "@material-tailwind/react";
import { EyeIcon, EyeSlashIcon, XMarkIcon } from "@heroicons/react/24/solid";
import { Link, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import api from "../../utils/Api";
import { GoogleLogin } from '@react-oauth/google';

export function SignIn() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [passwordShown, setPasswordShown] = useState(false);
  const [showTerms, setShowTerms] = useState(false);
  const togglePasswordVisiblity = () => setPasswordShown((cur) => !cur);
  const navigate = useNavigate();

  const handleOpenTerms = () => setShowTerms(true);
  const handleCloseTerms = () => setShowTerms(false);

  const clearMessages = () => {
    setTimeout(() => {
      setMessage("");
      setErrorMessage("");
    }, 4000);
  };

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      navigate("/dashboard/home");
    }

    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("verified") === "true") {
      setMessage("Account verified successfully! You can now log in.");
      clearMessages();
    }
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();

    try {
      const res = await api.post("/auth/login", {
        email,
        password,
      });

      // save token in localStorage
      localStorage.setItem("token", res.data.token);

      setMessage("Login successful! Redirecting...");
      clearMessages();
      setTimeout(() => {
        navigate("/dashboard/home"); // redirect to dashboard
      }, 4000);
    } catch (err) {
      console.error(err);
      setErrorMessage(err.response?.data?.message || "Invalid email or password");
      clearMessages();
    }
  };

  const handleGoogleLogin = async (credentialResponse) => {
    try {
      const res = await api.post("/auth/google-login", {
        token: credentialResponse.credential,
      });

      // save token in localStorage
      localStorage.setItem("token", res.data.token);
      if (res.data.user) {
        // optionally store user info
        localStorage.setItem("user", JSON.stringify(res.data.user));
      }

      setMessage("Google Login successful! Redirecting...");
      clearMessages();
      setTimeout(() => {
        navigate("/dashboard/home"); // redirect to dashboard
      }, 4000);
    } catch (err) {
      console.error("Backend Error:", err.response?.data || err.message);
      setErrorMessage("Google Login failed: " + (err.response?.data?.message || err.message));
      clearMessages();
    }
  };

  return (
    <section className="m-8 flex gap-4">
      <div className="w-full lg:w-3/5 mt-24">
        <div className="text-center">
          <Typography variant="h2" className="font-bold mb-4">
            Sign In
          </Typography>
          <Typography
            variant="paragraph"
            color="blue-gray"
            className="text-lg font-normal"
          >
            Enter your email and password to Sign In.
          </Typography>
        </div>

        {message && (
          <div className="mt-4 p-3 bg-green-100 text-green-700 rounded-lg text-center font-medium border border-green-200">
            {message}
          </div>
        )}
        {errorMessage && (
          <div className="mt-4 p-3 bg-red-100 text-red-700 rounded-lg text-center font-medium border border-red-200">
            {errorMessage}
          </div>
        )}

        <form
          className="mt-8 mb-2 mx-auto w-80 max-w-screen-lg lg:w-1/2"
          onSubmit={handleLogin}
        >
          <div className="mb-6 flex flex-col gap-6">
            <div>
              <Typography
                variant="small"
                color="blue-gray"
                className="mb-2 font-medium"
              >
                Your Email
              </Typography>
              <Input
                size="lg"
                type="email"
                label="Email"

                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required

              />
            </div>

            <div className="relative">
              <Typography
                variant="small"
                color="blue-gray"
                className="mb-2 font-medium"
              >
                Password
              </Typography>
              <Input
                size="lg"
                type={passwordShown ? "text" : "password"}
                label="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="pr-20"
                containerProps={{
                  className: "min-w-0",
                }}
              />
              <i onClick={togglePasswordVisiblity} className="absolute right-3 top-[38px] cursor-pointer z-10">
                {passwordShown ? (
                  <EyeIcon className="h-5 w-5" />
                ) : (
                  <EyeSlashIcon className="h-5 w-5" />
                )}
              </i>
            </div>
          </div>

          <Checkbox
            label={
              <Typography
                variant="small"
                color="gray"
                className="flex items-center justify-start font-medium"
              >
                I agree the&nbsp;
                <span
                  onClick={handleOpenTerms}
                  className="font-normal text-black transition-colors hover:text-gray-900 underline cursor-pointer"
                >
                  Terms and Conditions
                </span>
              </Typography>
            }
            containerProps={{ className: "-ml-2.5" }}
          />

          <Button type="submit" className="mt-6" fullWidth>
            Sign In
          </Button>

          <div className="mt-6 flex flex-col items-center justify-center gap-4">
            <Typography variant="small" className="font-medium text-gray-600">
              Or sign in with
            </Typography>
            <GoogleLogin
              onSuccess={handleGoogleLogin}
              onError={(err) => {
                console.log('Login Failed', err);
                setErrorMessage("Google Login Error: The application could not connect to Google. This is usually caused by an unauthorized origin (Port mismatch). Please ensure you are opening http://localhost:5173.");
              }}
            />
          </div>

          <Typography
            variant="paragraph"
            className="text-center text-blue-gray-500 font-medium mt-4"
          >
            Not registered?
            <Link to="/auth/sign-up" className="text-gray-900 ml-1">
              Create account
            </Link>
          </Typography>
        </form>
      </div>

      <div className="w-2/5 h-full hidden lg:block">
        <img
          src="/img/pattern.png"
          className="h-full w-full object-cover rounded-3xl"
        />
      </div>
      <Dialog open={showTerms} handler={handleCloseTerms} size="lg" className="p-4 rounded-2xl shadow-2xl">
        <DialogHeader className="flex justify-between items-center border-b border-gray-100 pb-4">
          <Typography variant="h4" color="blue-gray" className="font-bold">
            Terms and Conditions
          </Typography>
          <XMarkIcon
            className="h-6 w-6 cursor-pointer text-gray-500 hover:text-gray-900"
            onClick={handleCloseTerms}
          />
        </DialogHeader>
        <DialogBody divider className="overflow-y-auto max-h-[60vh] py-6 leading-relaxed text-gray-700">
          <div className="space-y-6">
            <section>
              <h3 className="text-lg font-bold text-gray-900 mb-2">1. Acceptance of Terms</h3>
              <p>By accessing and using this dashboard, you accept and agree to be bound by the terms and provision of this agreement.</p>
            </section>
            <section>
              <h3 className="text-lg font-bold text-gray-900 mb-2">2. Use License</h3>
              <p>Permission is granted to temporarily access the dashboard for personal, non-commercial transitory viewing only.</p>
            </section>
            <section>
              <h3 className="text-lg font-bold text-gray-900 mb-2">3. User Data & Privacy</h3>
              <p>Your privacy is important to us. We collect and use information as outlined in our Privacy Policy. By signing up, you consent to our data collection practices.</p>
            </section>
            <section>
              <h3 className="text-lg font-bold text-gray-900 mb-2">4. Prohibited Conduct</h3>
              <p>You agree not to use the dashboard for any unlawful purpose or any purpose prohibited under this clause. You agree not to use the dashboard in any way that could damage the dashboard, services, or general business of Honeybee Digital.</p>
            </section>
            <section>
              <h3 className="text-lg font-bold text-gray-900 mb-2">5. Termination</h3>
              <p>We reserve the right to terminate your access to the dashboard, without any advance notice, for any violation of these terms.</p>
            </section>
            <section>
              <h3 className="text-lg font-bold text-gray-900 mb-2">6. Governing Law</h3>
              <p>These terms and conditions are governed by and construed in accordance with the laws of the jurisdiction in which Honeybee Digital operates.</p>
            </section>
          </div>
        </DialogBody>
        <DialogFooter className="pt-4 border-t border-gray-100">
          <Button
            variant="gradient"
            color="gray"
            onClick={handleCloseTerms}
            className="rounded-xl px-8"
          >
            <span>Close</span>
          </Button>
        </DialogFooter>
      </Dialog>
    </section >
  );
}

// export default SignIn;
