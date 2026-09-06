export default function Card({ className = "", children, ...rest }) {
  return (
    <div
      className={`rounded-card border border-border bg-card p-5 shadow-soft ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}
