import { initializeApp, getApps, getApp } from 'firebase/app';
import { initializeAuth, getReactNativePersistence } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Replace these placeholders with your actual Firebase project configuration details
const firebaseConfig = {
  apiKey: "AIzaSyA0X_kh0kdTdkXSC1VTDm-J38tSnyZ36bo",
  authDomain: "smartlocker-67da4.firebaseapp.com",
  projectId: "smartlocker-67da4",
  storageBucket: "smartlocker-67da4.firebasestorage.app",
  messagingSenderId: "509975100156",
  appId: "1:509975100156:web:6c57bfc5b3de5670d0b579",
  measurementId: "G-6361TMH7FC"
};

// Initialize Firebase App
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();

// Initialize Auth with Native Persistence
const auth = initializeAuth(app, {
  persistence: getReactNativePersistence(AsyncStorage)
});

// Initialize Firestore Database Client
const db = getFirestore(app);

export { app, auth, db };
