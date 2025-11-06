## This file contains the current progress of this project, ordered by date.
## For the overall summary and goals of the project, check #README.md

### October 20, Monday:

Set up the first meeting between the supervisor and project members to discuss the project's direction. What we have agreed on so far:

- Using an NILM model to extract the load of each appliance in a household based on existing data of electricity bills
          
- Focusing only on residential areas
          
- Possibly establishing a connection with the Jordanian electricity provider (JEPCO)
          
- Downloading Linux on our devices to work with

### October 23, Thursday:

Due to some connections, we were able to visit JO Petrol to ask if they have any data they can give us, and they gave us the following advice:

- They helped us by telling us that PSUT has a deal with JEPCO, and we can use it to obtain data
          
- At this time, we are in contact with 3 executives in JO Petrol: 
          
  - Eng. Walaa Mubarak: a PSUT graduate who helped us with some background info on PSUT graduation protocols, and is available to answer any questions.
                    
  - Eng. Abed Balbisi: a senior engineer who gave us some background info on some electricity terms and gave us advice on what to focus on in our project,
    and is available to answer any questions.
                      
  - Eng. Yousef AlAdaileh:  a senior engineer who gave us some background info on some electricity terms and gave us advice on what to focus on in our project,
    and is available to answer any questions.

Some of the points they mentioned:

- An offer to work with us on another project in case our current project fell through due to a lack of data
          
- Gave us advice and more information as to what kind of data we should be looking for, and some basic information on smart meters 

Important point to mention:

- Eng. Yousef AlAdaileh has contacted JEPCO on our behalf and obtained the name of the university's Dr., Dr. Fadi, who signed the contract, then called Mariam to inform her of the name.

### October 26, Sunday: 

- We went to the university's dean’s office to inquire about the deal with JEPCO, who then sent us to Dr. Hashem (the university's external affairs director(?)),
  who then established contact with JEPCO on our behalf to inquire about the deal and whether we can use it to obtain the data that we need.
            
- He also mentioned that we send him an email explaining what kind of data we need to ask from JEPCO.

- We sent an email to our supervisor, Dr. Samer, requesting his guidance on the exact type, format, and intervals of data we should ask for from JEPCO to ensure it aligns with our project goals, and received his feedback and clarifications.

### October 27, Monday:

We sent the email to Dr. Hashem describing our project and specfiying the requested data, and waited for his reply.

### October 30, Thursday:

- Dr. Hashem reached back to us through email to meet him in his office, and as we did, he gave us the number of an executive, Dr. Imad, at JEPCO to establish contact with.
He specifically mentioned letting our supervisor, Dr. Samer, contact the JEPCO executive to arrange a meeting.

- Eng. Mohammad Alhamarsheh, another executive from JO Petrol, reached out to us and informed us that they have data that we might find useful, so we arranged to meet on Sunday, November 2nd.

### November 2, Sunday:

- Dr. Samer contacted Dr. Imad and agreed to talk on Wednesday, November 5th.

- We went to JO Petrol as agreed to check on the data, and Eng. Mohammad offered us a multitude of things:
  - He has given us an entire 200-page hardcopy thesis of his own Bachelor's graduation project, which included some elements that could be very useful for our own.
   
  - He has offered a hardware socket that can measure the electrical details of whatever appliance is connected to it, and its data can be accessed using an app.
    
  - We have declined taking this hardware because even if we did, we would need multiple of them to be plugged into for an entire year for the data to be relevant to our case.
    
  - Despite that, we agreed to take ALL the data he has offered, which can be useful for training the model on the average electricity consumption of most household electrical items.

- Eng. Mohammad has also given us a multitude of points to consider:
  
  - Jordan DOES NOT have a varying electricity bill that is based on peak hours, but on tiers that range in the following:
    
    (NOTE: numbers below may not be accurate)
    
    - For Non-Subsidised tariffs: 20 piasters/kW for all usages of electricity
       
    - For Subsidised tariffs with a monthly usage of:
      
      - 0-300 kW: 10 piasters/kW
        
      - 300-600 kW: 15 piasteres/kW
        
      - 600 kW and above: 20 piasters/kW
     
  - An average household has an average electricity consumption of 15-20 kW per day.
 
  - Although electricity bills are not influenced by peak hours, they are still relevant. The peak hours in Jordan (according to Eng. Mohammad) are 7 PM to 9 PM,
    which is after employees go home, and the average consumption at this time is 4.9 gW. The normal electricity consumption is 2.7-3.9 gW.
 
### November 6, Thursday:

We had a meeting with **Dr. Imad** from **JEPCO** to discuss the availability and structure of the electricity data we will be using for our project.

*   Dr. Imad informed us that the dataset will be shared with us in a few days.

    *   The data covers **multiple residential areas across Jordan** and we asked for it to be **around 1 to 2 years**.

    *   It contains all the detailed electrical measurements we would need.

*   He also explained that the data is recorded by **smart meters**, which are **not yet installed in all households** across Jordan this is why there are **no peak-hour based tariffs** for residential users.

*   The **data granularity** is **every 30 minutes**.

    *   This level of granularity is lower than what's typically ideal for **NILM**, which usually needs readings every 3--5 minutes.

    *   Because of this, we plan to **interpolate** the data to achieve a 10 minutes granularity or better if possible, allowing us to still be able to continue with **NILM**.


















