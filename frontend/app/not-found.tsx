import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md px-4 py-32 text-center">
      <h1 className="font-display text-2xl text-white">404</h1>
      <p className="mt-2 text-gray-400">Page not found.</p>
      <Link href="/" className="mt-6 inline-block text-mint-400 hover:underline">
        Home
      </Link>
    </div>
  );
}
