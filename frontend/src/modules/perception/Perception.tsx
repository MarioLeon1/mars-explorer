import { useParams } from 'react-router-dom'
import '../explorer/explorer.css'
import { PerceptionHome } from './PerceptionHome'
import './perception.css'
import { Workspace } from './Workspace'

/** `/perception` → image picker + benchmark; `/perception/:imageId` → analysis workspace. */
export function Perception() {
  const { imageId } = useParams()
  return imageId ? <Workspace key={imageId} imageId={imageId} /> : <PerceptionHome />
}
