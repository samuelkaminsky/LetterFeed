"use client"

import { useSyncExternalStore } from "react"

const subscribe = () => () => {}
const getSnapshot = () => window.location.origin
const getServerSnapshot = () => ""

/**
 * Returns window.location.origin on the client and "" during server
 * rendering and hydration, so callers can build absolute URLs without a
 * hydration mismatch or a setState-in-effect.
 */
export const useOrigin = () =>
  useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)

export const toAbsoluteUrl = (url: string, origin: string) =>
  url.startsWith("http://") || url.startsWith("https://") ? url : `${origin}${url}`
