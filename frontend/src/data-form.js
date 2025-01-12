import { useState } from 'react';
import {
    Box,
    Button,
    Paper,
    Typography,
    CircularProgress
} from '@mui/material';
import axios from 'axios';

const endpointMapping = {
    'Notion': 'notion',
    'Airtable': 'airtable',
};

export const DataForm = ({ integrationType, credentials }) => {
    const [loadedData, setLoadedData] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const endpoint = endpointMapping[integrationType];

   const handleLoad = async () => {
    try {
        const formData = new FormData();
        formData.append('credentials', JSON.stringify(credentials));
        // This endpoint should match what's in main.py
        const response = await axios.post(`http://localhost:8000/integrations/${endpoint}/load`, formData);
        const data = response.data;
        setLoadedData(data);
        console.log('Loaded data:', data); // For debugging
    } catch (e) {
        console.error('Error:', e); // For debugging
        alert(e?.response?.data?.detail);
    }
}

    const renderData = () => {
        if (!loadedData) return null;

        return (
            <Paper className="mt-4 p-4 max-h-96 overflow-auto">
                {loadedData.map((item, index) => (
                    <Box key={item.id || index} className="mb-4 p-3 bg-gray-50 rounded">
                        <Typography variant="subtitle1" className="font-medium">
                            {item.name || 'Unnamed'}
                        </Typography>
                        <Typography variant="body2" className="text-gray-600">
                            Type: {item.type}
                        </Typography>
                        {item.parent_path_or_name && (
                            <Typography variant="body2" className="text-gray-600">
                                Parent: {item.parent_path_or_name}
                            </Typography>
                        )}
                    </Box>
                ))}
            </Paper>
        );
    };

    return (
        <Box className="w-full max-w-2xl mt-4">
            <Box className="flex gap-2 justify-center">
                <Button
                    onClick={handleLoad}
                    variant="contained"
                    disabled={isLoading}
                >
                    {isLoading ? (
                        <CircularProgress size={24} className="text-white" />
                    ) : (
                        'Load Data'
                    )}
                </Button>
                <Button
                    onClick={() => setLoadedData(null)}
                    variant="outlined"
                    disabled={!loadedData}
                >
                    Clear Data
                </Button>
            </Box>

            {loadedData && (
                <Typography variant="subtitle2" className="mt-4 text-gray-600 text-center">
                    Loaded {loadedData.length} items
                </Typography>
            )}

            {renderData()}
        </Box>
    );
};

export default DataForm;