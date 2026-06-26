import React, { useState } from 'react';
import { 
  StyleSheet, 
  Text, 
  View, 
  TextInput, 
  TouchableOpacity, 
  ActivityIndicator, 
  KeyboardAvoidingView, 
  Platform,
  ScrollView 
} from 'react-native';
import { signInWithEmailAndPassword, createUserWithEmailAndPassword } from 'firebase/auth';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { auth } from '../services/firebaseConfig';
import { API_BASE_URL } from '../services/apiConfig';

export default function AuthScreen() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handleAuthAction = async () => {
    if (!email || !password) {
      setErrorMsg('Please enter both email and password.');
      return;
    }
    if (!isLogin && (!fullName || !phone)) {
      setErrorMsg('Please enter your full name and phone number.');
      return;
    }
    setErrorMsg('');
    setLoading(true);

    try {
      if (isLogin) {
        // 1. Sign in to Firebase Auth
        const firebaseUser = await signInWithEmailAndPassword(auth, email, password);
        
        // 2. Log in to Flask Backend to get JWT
        const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ email, password })
        });
        const loginData = await response.json();
        
        if (loginData.success) {
          // Store token in AsyncStorage
          await AsyncStorage.setItem('jwt_token', loginData.data.token);
          await AsyncStorage.setItem('user_info', JSON.stringify(loginData.data.user));
        } else {
          throw new Error(loginData.message || 'Flask backend login failed');
        }
      } else {
        // 1. Sign up on Firebase Auth
        const firebaseUser = await createUserWithEmailAndPassword(auth, email, password);
        
        // 2. Register on Flask Backend
        const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            full_name: fullName,
            phone: phone,
            email: email,
            password: password
          })
        });
        const registerData = await response.json();
        
        if (registerData.success) {
          // Registration succeeded, proceed to log in to Flask
          const loginResponse = await fetch(`${API_BASE_URL}/api/auth/login`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
          });
          const loginData = await loginResponse.json();
          if (loginData.success) {
            await AsyncStorage.setItem('jwt_token', loginData.data.token);
            await AsyncStorage.setItem('user_info', JSON.stringify(loginData.data.user));
          }
        } else {
          throw new Error(registerData.message || 'Flask backend registration failed');
        }
      }
    } catch (err) {
      console.error(err);
      setErrorMsg(err.message || 'Authentication failed. Please check your network and credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView 
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <ScrollView contentContainerStyle={styles.scrollContainer} keyboardShouldPersistTaps="handled">
        <View style={styles.card}>
          <Text style={styles.title}>Smart Locker</Text>
          <Text style={styles.subtitle}>
            {isLogin ? 'Log in to rent a secure locker' : 'Create an account to get started'}
          </Text>

          {errorMsg ? <Text style={styles.errorText}>{errorMsg}</Text> : null}

          {!isLogin && (
            <>
              <View style={styles.inputGroup}>
                <Text style={styles.label}>Full Name</Text>
                <TextInput
                  style={styles.input}
                  placeholder="Your Name"
                  placeholderTextColor="#a3a3a3"
                  value={fullName}
                  onChangeText={setFullName}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>Phone Number</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g. 7019007474"
                  placeholderTextColor="#a3a3a3"
                  keyboardType="phone-pad"
                  value={phone}
                  onChangeText={setPhone}
                />
              </View>
            </>
          )}

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Email Address</Text>
            <TextInput
              style={styles.input}
              placeholder="name@domain.com"
              placeholderTextColor="#a3a3a3"
              keyboardType="email-address"
              autoCapitalize="none"
              value={email}
              onChangeText={setEmail}
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              placeholder="••••••••"
              placeholderTextColor="#a3a3a3"
              secureTextEntry
              autoCapitalize="none"
              value={password}
              onChangeText={setPassword}
            />
          </View>

          <TouchableOpacity 
            style={styles.button} 
            onPress={handleAuthAction}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#000000" />
            ) : (
              <Text style={styles.buttonText}>{isLogin ? 'Log In' : 'Sign Up'}</Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity 
            style={styles.switchButton}
            onPress={() => {
              setIsLogin(!isLogin);
              setErrorMsg('');
            }}
          >
            <Text style={styles.switchText}>
              {isLogin ? "Don't have an account? Sign Up" : 'Already have an account? Log In'}
            </Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#040807',
  },
  scrollContainer: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  card: {
    backgroundColor: '#0a1412',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#132c25',
    padding: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 6,
    elevation: 8,
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#10b981',
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: '#6ee7b7',
    textAlign: 'center',
    marginBottom: 24,
  },
  errorText: {
    color: '#ef4444',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#ef4444',
    padding: 8,
    borderRadius: 4,
  },
  inputGroup: {
    marginBottom: 16,
  },
  label: {
    color: '#e6f4f1',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#11231f',
    color: '#e6f4f1',
    borderWidth: 1,
    borderColor: '#1d3d36',
    height: 48,
    borderRadius: 4,
    paddingHorizontal: 16,
    fontSize: 16,
  },
  button: {
    backgroundColor: '#10b981',
    height: 48,
    borderRadius: 4,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 16,
  },
  buttonText: {
    color: '#040807',
    fontSize: 16,
    fontWeight: 'bold',
  },
  switchButton: {
    marginTop: 20,
    alignItems: 'center',
  },
  switchText: {
    color: '#14b8a6',
    fontSize: 14,
    textDecorationLine: 'underline',
  },
});
