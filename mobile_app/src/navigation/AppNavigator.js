import React, { useState, useEffect } from 'react';
import { createStackNavigator } from '@react-navigation/stack';
import { NavigationContainer } from '@react-navigation/native';
import { onAuthStateChanged } from 'firebase/auth';
import { auth } from '../services/firebaseConfig';

import AuthScreen from '../screens/AuthScreen';
import HomeScreen from '../screens/HomeScreen';
import PaymentScreen from '../screens/PaymentScreen';
import TimerScreen from '../screens/TimerScreen';
import RetrievalScreen from '../screens/RetrievalScreen';
import { ActivityIndicator, View } from 'react-native';

const Stack = createStackNavigator();

export default function AppNavigator() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (usr) => {
      setUser(usr);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  if (loading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#040807' }}>
        <ActivityIndicator size="large" color="#10b981" />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: '#0a1412', borderBottomWidth: 1, borderBottomColor: '#132c25' },
          headerTintColor: '#10b981',
          headerTitleStyle: { fontWeight: 'bold' },
          cardStyle: { backgroundColor: '#040807' }
        }}
      >
        {user ? (
          <>
            <Stack.Screen name="Home" component={HomeScreen} options={{ title: 'Smart Locker' }} />
            <Stack.Screen name="Payment" component={PaymentScreen} options={{ title: 'Confirm Payment' }} />
            <Stack.Screen name="Timer" component={TimerScreen} options={{ title: 'Locker Session' }} />
            <Stack.Screen name="Retrieval" component={RetrievalScreen} options={{ title: 'Retrieve Belongings' }} />
          </>
        ) : (
          <Stack.Screen name="Auth" component={AuthScreen} options={{ headerShown: false }} />
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
