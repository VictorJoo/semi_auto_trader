export default function EmptyItem({ text }: { text: string }) {
  return (
    <div className="item">
      <span>{text}</span>
    </div>
  )
}
