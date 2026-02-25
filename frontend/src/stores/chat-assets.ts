import { create } from 'zustand'
import type { Asset } from '../types'

interface ChatAssetState {
  assets: Record<string, Asset[]> // chatId -> assets
  setAssets: (chatId: string, assets: Asset[]) => void
  addAsset: (chatId: string, asset: Asset) => void
  deleteAsset: (chatId: string, assetId: string) => void
}

export const useChatAssetStore = create<ChatAssetState>()((set) => ({
  assets: {},

  setAssets: (chatId, assets) =>
    set((state) => ({
      assets: { ...state.assets, [chatId]: assets },
    })),

  addAsset: (chatId, asset) =>
    set((state) => ({
      assets: {
        ...state.assets,
        [chatId]: [asset, ...(state.assets[chatId] || [])],
      },
    })),

  deleteAsset: (chatId, assetId) =>
    set((state) => ({
      assets: {
        ...state.assets,
        [chatId]: (state.assets[chatId] || []).filter((a) => a.id !== assetId),
      },
    })),
}))
