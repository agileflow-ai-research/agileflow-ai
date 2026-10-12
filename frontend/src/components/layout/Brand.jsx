import agileflowMark from '../../assets/brand/agileflow-mark.png'
import agileflowWordmark from '../../assets/brand/agileflow-wordmark-dark.png'

function Brand() {
  return (
    <div className="flex items-center gap-3" aria-label="AgileFlow AI">
      <img
        className="h-9 w-9 object-contain"
        src={agileflowMark}
        alt=""
        aria-hidden="true"
      />
      <img
        className="h-7 w-auto max-w-40 object-contain"
        src={agileflowWordmark}
        alt="AgileFlow AI"
      />
    </div>
  )
}

export default Brand
