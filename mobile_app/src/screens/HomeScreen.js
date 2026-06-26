import React, { useState, useEffect } from 'react';
import { 
  StyleSheet, 
  Text, 
  View, 
  TouchableOpacity, 
  ActivityIndicator, 
  Alert,
  FlatList,
  Linking
} from 'react-native';
import { collection, query, where, onSnapshot } from 'firebase/firestore';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { auth, db } from '../services/firebaseConfig';
import { API_BASE_URL } from '../services/apiConfig';
import { signOut } from 'firebase/auth';

export default function HomeScreen({ navigation }) {
  const [lockers, setLockers] = useState([]);
  const [selectedLocker, setSelectedLocker] = useState(null);
  const [durationHours, setDurationHours] = useState(1);
  const [loading, setLoading] = useState(false);
  const [activeBooking, setActiveBooking] = useState(null);
  const [checkingActive, setCheckingActive] = useState(true);

  // 1. Listen for active bookings in Firestore (Real-time synchronization)
  useEffect(() => {
    if (!auth.currentUser) return;
    
    const email = auth.currentUser.email;
    const q = query(
      collection(db, "bookings"),
      where("email", "==", email)
    );

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const active = snapshot.docs
        .map(doc => ({ id: doc.id, ...doc.data() }))
        .find(b => ["pending_payment", "waiting_for_door_close", "active_rental", "otp_generated", "retrieval_approved"].includes(b.booking_status));
      
      setActiveBooking(active || null);
      setCheckingActive(false);

      if (active) {
        // Automatically route based on current state
        if (active.booking_status === "pending_payment" || active.booking_status === "waiting_for_door_close") {
          navigation.navigate("Payment", { bookingId: active.booking_id });
        } else if (active.booking_status === "active_rental" || active.booking_status === "otp_generated") {
          navigation.navigate("Timer", { bookingId: active.booking_id });
        } else if (active.booking_status === "retrieval_approved") {
          navigation.navigate("Retrieval", { bookingId: active.booking_id });
        }
      }
    }, (error) => {
      console.error("Firestore bookings sync error:", error);
      setCheckingActive(false);
    });

    return unsubscribe;
  }, [navigation]);

  // 2. Listen for locker list in Firestore (Real-time updates)
  useEffect(() => {
    const q = query(collection(db, "lockers"));
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const lockerList = snapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data()
      }));
      setLockers(lockerList);
      
      // Default select first available locker if none selected
      if (lockerList.length > 0 && !selectedLocker) {
        const firstAvail = lockerList.find(l => l.status === 'available');
        if (firstAvail) setSelectedLocker(firstAvail.locker_id);
      }
    }, (error) => {
      console.error("Firestore lockers sync error:", error);
    });

    return unsubscribe;
  }, [selectedLocker]);

  const handleCreateBooking = async () => {
    if (!selectedLocker) {
      Alert.alert("Error", "Please select an available locker.");
      return;
    }
    
    setLoading(true);
    try {
      const token = await AsyncStorage.getItem('jwt_token');
      if (!token) {
        throw new Error("User JWT token not found. Please log in again.");
      }

      const response = await fetch(`${API_BASE_URL}/api/bookings/create`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          locker_id: selectedLocker,
          rental_duration: durationHours * 60 // Convert hours to minutes
        })
      });

      const data = await response.json();
      if (!data.success) {
        throw new Error(data.message || "Failed to create booking");
      }

      // Success: Firebase sync on the backend will automatically sync this booking, 
      // trigger our onSnapshot, and route the user to the Payment view.
      Alert.alert("Success", "Booking created! Proceed to payment.");
    } catch (error) {
      console.error(error);
      Alert.alert("Booking Failed", error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await AsyncStorage.removeItem('jwt_token');
      await AsyncStorage.removeItem('user_info');
      await signOut(auth);
    } catch (e) {
      console.error(e);
    }
  };

  if (checkingActive) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#ffffff" />
        <Text style={styles.loadingText}>Syncing state with locker database...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {activeBooking ? (
        <View style={styles.activeContainer}>
          <Text style={styles.activeTitle}>Active Rental Found</Text>
          <Text style={styles.activeText}>Locker: {activeBooking.locker_id}</Text>
          <Text style={styles.activeText}>Status: {activeBooking.booking_status.replace(/_/g, ' ').toUpperCase()}</Text>
          <TouchableOpacity 
            style={styles.activeButton}
            onPress={() => {
              if (activeBooking.booking_status === "pending_payment" || activeBooking.booking_status === "waiting_for_door_close") {
                navigation.navigate("Payment", { bookingId: activeBooking.booking_id });
              } else if (activeBooking.booking_status === "active_rental" || activeBooking.booking_status === "otp_generated") {
                navigation.navigate("Timer", { bookingId: activeBooking.booking_id });
              } else if (activeBooking.booking_status === "retrieval_approved") {
                navigation.navigate("Retrieval", { bookingId: activeBooking.booking_id });
              }
            }}
          >
            <Text style={styles.activeButtonText}>Resume Rental Session</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.bookingForm}>
          <Text style={styles.title}>Select Available Locker</Text>
          
          <FlatList
            data={lockers}
            keyExtractor={(item) => item.locker_id}
            contentContainerStyle={styles.gridList}
            renderItem={({ item }) => {
              const isSelected = selectedLocker === item.locker_id;
              const isAvailable = item.status === 'available';

              return (
                <TouchableOpacity
                  style={[
                    styles.gridCard,
                    !isAvailable && styles.cardDisabled,
                    isSelected && styles.cardSelected
                  ]}
                  disabled={!isAvailable}
                  onPress={() => setSelectedLocker(item.locker_id)}
                >
                  <Text style={[styles.cardText, isSelected && styles.cardTextSelected]}>
                    {item.locker_id}
                  </Text>
                  <Text style={[styles.cardSubText, isSelected && styles.cardTextSelected]}>
                    {isAvailable ? 'AVAILABLE' : item.status.toUpperCase()}
                  </Text>
                </TouchableOpacity>
              );
            }}
          />

          <View style={styles.durationSection}>
            <Text style={styles.sectionTitle}>Rental Duration</Text>
            <View style={styles.durationButtons}>
              {[1, 2, 4, 8].map((h) => (
                <TouchableOpacity
                  key={h}
                  style={[styles.durationBtn, durationHours === h && styles.durationBtnSelected]}
                  onPress={() => setDurationHours(h)}
                >
                  <Text style={[styles.durationText, durationHours === h && styles.durationTextSelected]}>
                    {h} {h === 1 ? 'hr' : 'hrs'}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            <View style={styles.pricingRow}>
              <Text style={styles.priceLabel}>Total Cost:</Text>
              <Text style={styles.priceValue}>₹{durationHours * 20}</Text>
            </View>
          </View>

          <TouchableOpacity 
            style={styles.rentButton}
            onPress={handleCreateBooking}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#000000" />
            ) : (
              <Text style={styles.rentButtonText}>Rent Locker Now →</Text>
            )}
          </TouchableOpacity>
        </View>
      )}

      <View style={styles.supportContainer}>
        <Text style={styles.supportLabel}>Help & Support:</Text>
        <TouchableOpacity style={styles.supportBtn} onPress={() => Linking.openURL('tel:7019007474')}>
          <Text style={styles.supportValue}>📞 7019007474</Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
        <Text style={styles.logoutText}>Log Out</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#040807',
    padding: 16,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#040807',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#e6f4f1',
    marginTop: 12,
    fontSize: 16,
  },
  title: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#10b981',
    marginBottom: 16,
  },
  gridList: {
    marginBottom: 20,
  },
  gridCard: {
    backgroundColor: '#0a1412',
    borderWidth: 1,
    borderColor: '#132c25',
    borderRadius: 6,
    padding: 16,
    marginBottom: 12,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cardSelected: {
    backgroundColor: '#10b981',
    borderColor: '#10b981',
  },
  cardDisabled: {
    borderColor: '#0b1614',
    opacity: 0.3,
  },
  cardText: {
    color: '#e6f4f1',
    fontSize: 16,
    fontWeight: 'bold',
  },
  cardTextSelected: {
    color: '#040807',
  },
  cardSubText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6ee7b7',
  },
  durationSection: {
    borderTopWidth: 1,
    borderTopColor: '#132c25',
    paddingVertical: 20,
  },
  sectionTitle: {
    color: '#e6f4f1',
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 12,
  },
  durationButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  durationBtn: {
    flex: 1,
    backgroundColor: '#0a1412',
    borderWidth: 1,
    borderColor: '#132c25',
    borderRadius: 4,
    height: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginHorizontal: 4,
  },
  durationBtnSelected: {
    backgroundColor: '#10b981',
    borderColor: '#10b981',
  },
  durationText: {
    color: '#e6f4f1',
    fontWeight: '600',
  },
  durationTextSelected: {
    color: '#040807',
  },
  pricingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
  },
  priceLabel: {
    color: '#6ee7b7',
    fontSize: 16,
  },
  priceValue: {
    color: '#10b981',
    fontSize: 22,
    fontWeight: 'bold',
  },
  rentButton: {
    backgroundColor: '#10b981',
    height: 52,
    borderRadius: 4,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 12,
  },
  rentButtonText: {
    color: '#040807',
    fontSize: 16,
    fontWeight: 'bold',
  },
  activeContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#0a1412',
    borderWidth: 1,
    borderColor: '#132c25',
    borderRadius: 8,
    padding: 24,
    marginVertical: 40,
  },
  activeTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#10b981',
    marginBottom: 16,
  },
  activeText: {
    color: '#6ee7b7',
    fontSize: 16,
    marginBottom: 8,
  },
  activeButton: {
    backgroundColor: '#10b981',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 4,
    marginTop: 24,
  },
  activeButtonText: {
    color: '#040807',
    fontSize: 16,
    fontWeight: 'bold',
  },
  supportContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#0a1412',
    borderWidth: 1,
    borderColor: '#132c25',
    borderRadius: 6,
    padding: 12,
    marginVertical: 12,
  },
  supportLabel: {
    color: '#6ee7b7',
    fontSize: 14,
    fontWeight: '600',
  },
  supportBtn: {
    backgroundColor: '#11231f',
    borderWidth: 1,
    borderColor: '#1d3d36',
    borderRadius: 4,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  supportValue: {
    color: '#10b981',
    fontSize: 14,
    fontWeight: 'bold',
  },
  logoutButton: {
    marginTop: 'auto',
    alignSelf: 'center',
    paddingVertical: 12,
  },
  logoutText: {
    color: '#ef4444',
    fontSize: 15,
    textDecorationLine: 'underline',
  },
  bookingForm: {
    flex: 1,
  }
});
